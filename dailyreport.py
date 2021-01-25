import requests
import base64
import json
import datetime
import re
import time
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from bs4 import BeautifulSoup as soup
import pickle
from tqdm import tqdm

WAIT = 120  # 多人上报时对方服务器报429错误时的等待时间
MAX_RETRY = 2  # 遇到429错误时的尝试次数
ADDR_1 = '嘉定校区内'  # 两报的校区
EMAIL = ''  # Email账号
EMAIL_PASS = ''  # Email口令
EMAIL_HOST = ''  # Email 服务器


def make_json(path):
    '''
    获取上报名单，并且制作json
    '''
    all_info = []
    for i in os.listdir(path):
        template = {"name": '',
                    'txt_file': '',
                    'stu_num': '',
                    'pass': '',
                    'cookie': '',
                    'addr_1': ADDR_1,
                    'addr_2': ''}
        if '.txt' in i:
            with open(os.path.join(path, i), 'r') as f:
                info = f.read().split()
                template['txt_file'] = i
                template['stu_num'] = info[0]
                template['pass'] = info[1]
                if len(info) > 2:
                    template['addr_1'] = info[2]
                all_info.append(template)
        json.dump(all_info, open('all_stu.json', 'w'), ensure_ascii=False)
    return all_info


def get_upload(path):
    '''
    获取上报模板
    '''
    with open(path, 'r', encoding='utf-8')as f:
        d = f.read()
    rt1 = {}
    for t in [i.split(': ') for i in d.splitlines()]:
        rt1[t[0]] = t[1]
    return rt1


def send_email(content, subject="每日一报不成功！！"):
    mail_host = EMAIL_HOST  # 设置服务器
    mail_user = EMAIL  # 用户名
    mail_pass = EMAIL_PASS  # 口令

    sender = EMAIL
    receivers = [EMAIL, ]  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱

    message = MIMEText(content, 'plain', 'utf-8')
    # message['From'] = Header("lans", 'utf-8')
    # message['To'] =  Header("lans", 'utf-8')
    message['From'] = sender
    message['To'] = ';'.join(receivers)
    message['Cc'] = sender

    subject = subject
    message['Subject'] = Header(subject, 'utf-8')

    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 25)    # 25 为 SMTP 端口号
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException as e:
        print(e)
        print("Error: 无法发送邮件")


class Dailyreport:
    '''
    单个同学上报
    '''

    def __init__(self, stu_dic):
        self.now = datetime.datetime.now()  # 获取当前时间
        self.date = self.now.date().strftime('%Y-%m-%d')  # 获取日期
        self.zone = 1 if self.now.hour < 20 else 2  # 早报晚报
        self.retry = 0  # 记录重复登录次数
        self.upload_status = 0  # 记录上报是否成功
        self.stu_dic = stu_dic  # 学生信息
        self.error = None  # 记录遇到的问题
        self.report = True  # 是否上报条件，假如为false则结束所有人的上报
        self.upload_data_1 = get_upload('once.txt')  # 一报模板
        self.upload_data_2 = get_upload('twice.txt')  # 两报模板
        self.cookie = False  # 记录是否使用cookie进行登录

        if self.stu_dic['cookie'] == '':
            self.sess = self.login()  # session
        else:
            self.sess = self.cookie_login()

        if self.report:
            self.one_or_two = self.check_one_or_two()  # 判断一报还是两报
            if self.one_or_two == 1:
                self.report_url = 'https://selfreport.shu.edu.cn/DayReport.aspx'
            elif self.one_or_two == 2:
                self.report_url = f'https://selfreport.shu.edu.cn/XueSFX/HalfdayReport.aspx?t={self.zone}'
            self.report_page = self.get_report_page()
            if self.stu_dic['name'] == '':
                self.stu_dic['name'] = self.get_name()  # 获取名字

            self.stu_dic['addr_2'] = self.get_addr_2()  # 获取地址
            self.viewstate, self.vgen = self.get_viewstate()  # 上报内容的加密字段获取
            self.f_state_dic = None
            self.f_state = self.get_f_state()
            self.upload_content = self.make_upload_data()  # 上报内容整合

    def login(self):
        '''
        最强登录法
        '''

        print("获取cookie")
        try:
            while True:
                sess = requests.Session()
                r = sess.get('https://selfreport.shu.edu.cn/')
                code = r.url.split('/')[-1]
                url_param = eval(base64.b64decode(code).decode("utf-8"))
                state = url_param['state']

                sess.post(r.url, data={
                    'username': self.stu_dic['stu_num'],
                    'password': self.stu_dic['pass'],
                    'login_submit': ''
                }, )
                r = sess.get(
                    f"https://newsso.shu.edu.cn/oauth/authorize?client_id=WUHWfrntnWYHZfzQ5QvXUCVy&response_type=code&scope=1&redirect_uri=https%3A%2F%2Fselfreport.shu.edu.cn%2FLoginSSO.aspx%3FReturnUrl%3D%252f&state={state}")
                if r.status_code == 200:
                    if r.url == 'https://selfreport.shu.edu.cn/':
                        self.stu_dic['cookie'] = f".ncov2019selfreport={dict(sess.cookies)['.ncov2019selfreport']}"
                        print(self.stu_dic['txt_file'], 'login succeed!')
                        break

                    else:
                        print("登录失败！疑似修改登录系统！")
                        self.error = '登录失败！疑似修改登录系统！'
                        self.report = False
                        print('url: ', r.url, r.status_code)
                        sess = None
                        break
                elif r.status_code == 429:
                    print(self.stu_dic['txt_file'], 'retrying ')
                    self.retry += 1
                    time.sleep(WAIT)
                    continue
                elif self.retry > MAX_RETRY:
                    self.error = 'Max tries exceeds...'
                    self.report = False
                    break
                else:
                    print(self.stu_dic['txt_file'], 'cannot login')
                    self.error = '登录失败！疑似修改登录系统！'
                    self.report = False
                    sess = None
                    break
            return sess

        except Exception as e:
            print(e, '\n')
            self.error = str(e)
            self.report = False
            if 'HTTPSConnectionPool' in str(e):
                print("Please check VPN")
            return None

    def cookie_login(self):
        '''
        使用cookie登录
        '''

        print("尝试使用cookie登录")
        sess = requests.Session()
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                   'Accept-Encoding': 'gzip, deflate, br',
                   'Accept-Language': 'zh-CN,zh;q=0.9',
                   'Connection': 'keep-alive',
                   'Cookie': f"{self.stu_dic['cookie']}",
                   'Host': 'selfreport.shu.edu.cn',
                   'Referer': 'https://selfreport.shu.edu.cn/XueSFX/FanXRB.aspx',
                   'Sec-Fetch-Dest': 'document',
                   'Sec-Fetch-Mode': 'navigate',
                   'Sec-Fetch-Site': 'same-origin',
                   'Sec-Fetch-User': '?1',
                   'Upgrade-Insecure-Requests': '1',
                   'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36', }
        sess.headers = headers
        html = sess.get("https://selfreport.shu.edu.cn/")
        if html.url != "https://selfreport.shu.edu.cn/":
            return self.login()
        else:
            self.cookie = True
            return sess
    
    def legacy_login(self):
        '''
        想加入selenium登录作为最后登录手段，但是selenium过于没有技术含量，而且速度慢、使用依赖过多，所以没写
        '''
        pass

    def get_name(self):
        '''
        获取上报者姓名
        '''

        if self.report:
            html = self.sess.get("https://selfreport.shu.edu.cn/")
            html = soup(html.text, 'lxml')
            name = html.find('span', {"id": "lbXingMing"}
                             ).text.strip().split("：")[1]
            return name
        else:
            return ''

    def check_one_or_two(self):
        if self.report:
            if '每日两报' in self.sess.get("https://selfreport.shu.edu.cn/").text:
                return 2
            elif "每日一报"in self.sess.get("https://selfreport.shu.edu.cn/").text:
                return 1
            else:
                self.error = '主页既没有一报也没有两报'
                return 0

    def get_addr_2_old(self):
        '''
        从离校申请中取地址，暂时弃用
        '''
        html1 = self.sess.get(
            "https://selfreport.shu.edu.cn/LiHLX/XueSLXLS.aspx")
        pat = re.compile(r'ViewXueSLX\.aspx\?id=\d+')
        inner_url = re.findall(pat, html1.text)[0]
        html2 = self.sess.get(
            f"https://selfreport.shu.edu.cn/LiHLX/{inner_url}")
        pat2 = re.compile(r'<span>(.{1,30})<\/span>')
        addr_info = re.findall(pat2, html2.text)
        return addr_info[:4]

    def get_addr_2(self):
        '''
        从上报的网址中获取地址信息
        '''

        if self.one_or_two == 2:
            return ''
        else:
            con = soup(self.report_page.text, 'lxml').findAll(
                'script', {'type': 'text/javascript'})[-1].text
            f_state_val = [i.strip().replace(';', '').split('=')[1]
                           for i in con.split('var') if '={' in i]

            try:
                addrs = []
                for i in f_state_val:
                    addrs.append(i)
                    if "国内详细地址" in i:
                        break
                return [eval(i.replace("true", 'True').replace('false', 'False')) for i in addrs[-4:]]
            except:
                addrs = []
                for i in f_state_val:
                    addrs.append(i)
                    if len(addrs) > 3 and '选择县区' in addrs[-2]:
                        break
                return [eval(i.replace("true", 'True').replace('false', 'False')) for i in addrs[-4:]]

    def get_report_page(self):
        '''
        获取上报网址的内容
        '''
        return self.sess.get(self.report_url)

    def get_viewstate(self):
        pattern = re.compile(
            r'name="__VIEWSTATE" id="__VIEWSTATE" value="[^"]+')
        viewstate = re.findall(pattern, self.report_page.text)[0]
        viewstate = viewstate[43:]
        pattern_1 = re.compile(r'id="__VIEWSTATEGENERATOR" value="[^"]+')
        vgen = re.findall(pattern_1, self.report_page.text)[0]
        vgen = vgen[vgen.find('value="')+7:]
        return viewstate, vgen

    def get_f_state(self):
        '''
        制作f_state, 一报需要分上海和非上海，因为填报的内容不一样
        '''

        if self.one_or_two == 2:
            a = self.upload_data_2['F_STATE']
            state = eval(str(base64.b64decode(a)))
            decoded = json.loads(state.decode('utf-8'))
            decoded['p1_BaoSRQ']['Text'] = self.date
            # 改校内地址
            decoded["p1_XiangXDZ"]['Text'] = self.stu_dic['addr_1']
            if datetime.datetime.now().hour > 20:
                decoded['p1']['title'] = '每日两报（下午）'
            f_state = base64.b64encode(
                bytes(json.dumps(decoded), encoding='utf-8'))
        elif self.one_or_two == 1:
            a_2 = self.upload_data_1['F_STATE']
            state_2 = eval(str(base64.b64decode(a_2)))
            decoded_2 = json.loads(state_2.decode('utf-8'))
            decoded_2['p1_BaoSRQ']['Text'] = self.date
            decoded_2["p1_ddlSheng"] = self.stu_dic['addr_2'][0]
            decoded_2["p1_ddlShi"] = self.stu_dic['addr_2'][1]
            decoded_2["p1_ddlXian"] = self.stu_dic['addr_2'][2]
            decoded_2["p1_XiangXDZ"]['Label'] = '国内详细地址（省市区县无需重复填写）'
            decoded_2["p1_XiangXDZ"]['Text'] = self.stu_dic['addr_2'][3]['Text']
            if self.stu_dic['addr_2'][0]['SelectedValueArray'][0] != '上海':
                decoded_2['p1_ShiFSH']['SelectedValue'] = '否'
                decoded_2['p1_ShiFZX']['SelectedValue'] = None
                decoded_2['p1_TongZWDLH']['SelectedValue'] = None
                decoded_2['p1_TongZWDLH']['Required'] = False
                decoded_2['p1_ShiFZX']['Hidden'] = True
            else:
                decoded_2['p1_ShiFZX']['Required'] = True
                decoded_2['p1_ShiFZX']['Hidden'] = False
                decoded_2['p1_ShiFSH']['SelectedValue'] = '是'
                decoded_2['p1_ShiFZX']['SelectedValue'] = "否"
                decoded_2['p1_TongZWDLH']['SelectedValue'] = '否'
                decoded_2['p1_TongZWDLH']['Required'] = True
                decoded_2['p1_ShiFZX']['Hidden'] = False

            self.f_state_dic = decoded_2
            f_state = base64.b64encode(
                bytes(json.dumps(decoded_2), encoding='utf-8'))
        return str(f_state)[2:-1]

    def make_upload_data(self):
        '''
        制作上报内容，一报仍然需要分上海和非上海
        '''
        if self.one_or_two == 1:
            upload_data = self.upload_data_1
            upload_data['p1$BaoSRQ'] = self.date
            upload_data['__VIEWSTATE'] = self.viewstate
            upload_data['__VIEWSTATEGENERATOR'] = self.vgen
            upload_data['F_STATE'] = self.f_state
            # 省
            upload_data['p1$ddlSheng$Value'] = self.stu_dic['addr_2'][0]['SelectedValueArray'][0]
            upload_data['p1$ddlSheng'] = self.stu_dic['addr_2'][0]['SelectedValueArray'][0]
            # 市
            upload_data['p1$ddlShi$Value'] = self.stu_dic['addr_2'][1]['SelectedValueArray'][0]
            upload_data['p1$ddlShi'] = self.stu_dic['addr_2'][1]['SelectedValueArray'][0]
            # 区县
            upload_data['p1$ddlXian$Value'] = self.stu_dic['addr_2'][2]['SelectedValueArray'][0]
            upload_data['p1$ddlXian'] = self.stu_dic['addr_2'][2]['SelectedValueArray'][0]
            # 详细地址
            upload_data['p1$XiangXDZ'] = self.stu_dic['addr_2'][3]['Text']
            if self.stu_dic['addr_2'][0]['SelectedValueArray'][0] != '上海':
                upload_data['p1$ShiFSH'] = '否'
            else:
                upload_data['p1$ShiFSH'] = '是'
                upload_data['p1$ShiFZX'] = '否'
                upload_data['p1$TongZWDLH'] = '否'

        else:
            upload_data = self.upload_data_2
            upload_data['p1$BaoSRQ'] = self.date
            upload_data['__VIEWSTATE'] = self.viewstate
            upload_data['__VIEWSTATEGENERATOR'] = self.vgen
            upload_data['F_STATE'] = self.f_state
            upload_data['p1$XiangXDZ'] = self.stu_dic['addr_1']
        return upload_data

    def upload(self):
        '''
        上报
        '''

        if self.report:
            final = self.sess.post(self.report_url, data=self.upload_content)
            if '提交成功' in final.text:
                self.upload_status = 1
                print(self.stu_dic['name'], 'done')
            else:
                with open('{}_{}.log'.format(self.stu_dic['name'], self.date), 'w') as f:
                    f.write(final.text)
                print(self.stu_dic['name'], 'failed')
        else:
            print("You fucked up")
        return self


class Manager:
    '''
    控制多人上报的一些事宜，比如遇到429错误时的等待、
    发送上报失败和成功的邮件，统计上报的一些数据啥的，还没写完，能用，先这样吧
    '''

    def __init__(self, students):
        self.students = students
        self.success = []
        self.failed = []
        self.sys_fail = False
        self.check_result = []

    def check(self):
        n = 0
        for i in self.students:
            if n % 5 == 0 and n != 0:
                for _ in tqdm(range(WAIT)):
                    time.sleep(1)
            dc = Dailyreport(i)
            self.check_result.append(dc)
            if dc.report == False:
                self.sys_fail = True
                break
            if not dc.cookie:
                n += 1
            if dc.retry > 0:
                n = 1
        pickle.dump(self.check_result, open('check_result.pkl', 'wb'))

    def run(self):
        n = 0
        for i in self.students:
            if n % 5 == 0 and n != 0:
                for _ in tqdm(range(WAIT)):
                    time.sleep(1)
            dr = Dailyreport(i).upload()
            print('\n')
            if dr.report == False:
                self.sys_fail = True
                break
            if dr.upload_status == 1:
                self.success.append(dr)
            else:
                self.failed.append(dr)
            if not dr.cookie:
                n += 1
            if dr.retry > 0:
                n = 1
        return self

    def send(self):
        if len(self.success) == len(self.students):
            send_email(
                f'一报的人有{len([i for i in self.success if i.one_or_two == 1])}个\n两报的人有{len([i for i in self.success if i.one_or_two != 1])}个\n ', "又是美好的一天")
        else:
            send_email('failed: {}\nsuccess: {}'.format(";".join([str((i.stu_dic['name'], i.one_or_two, i.stu_dic['txt_file'])) for i in self.failed]), ";".join(
                [str((i.stu_dic['name'], i.one_or_two)) for i in self.success])))


if __name__ == '__main__':
    if os.path.exists('all_stu.json'):
        all_stu = json.load(open('all_stu.json', 'r'))
    else:
        all_stu = make_json("students")
    manage = Manager(all_stu)
    manage.run()
    # manage.send()
    if len(manage.failed) != 0:
        json.dump([i.stu_dic for i in manage.failed], open(
            'all_stu_failed.json', 'w'), ensure_ascii=False) #记录上报没成功的人
    json.dump(all_stu, open('all_stu.json', 'w'), ensure_ascii=False)
