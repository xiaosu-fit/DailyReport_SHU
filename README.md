# DailyReport_SHU

受@BlueFisher大神所启发的项目，已经自己使用3个月。如下是与@BlueFisher大神项目不同之处，希望能对大家有所帮助

* 能自行识别一报和两报
* 一报根据前一天上报的地址进行填报，无需自己手动配置地址 
* 一报根据所在地调整上报内容（上海和外地的上报选项会有所差别），所以只需要知道学生学号密码即可上报
* 对多人上报进行优化，短时间内多次登录服务器会报429错误，因此代码中有加入休眠机制
* 没有github action
* 没有一键自动补报



## 更新

* 解决了对lxml库的依赖
* 改变了一报动态取地址的网址，之前是从上报网址中取默认内容，现在改为从上报历史中取前一天上报的地址
* 解决了个别系统取地址时报index error的问题
* 加入`students`文件夹和`all_stu.json`文件内容的同步模块，解决了后续加入的上报同学不加入all_stu.json的问题。


## 免责声明

本项目仅做免费的学术交流使用。请勿做商业用途！！



## 依赖

* Python >= 3.7

* requests
* bs4
* tqdm

版本无所谓



## 文件说明

- ` once.txt`和`twice.txt`分别为每日一报和两报的上传模板
- students文件夹中存放学上学号密码，支持多人上报



## 用法

1. 假如需要使用一报时一定要自己上报过至少一天！！！！

2. 在students文件夹中加入txt文件记录学生学号和密码，具体格式如`stu_1.txt`所示，想要多人上报的话直接在students文件夹下另外新建txt，命名无所谓。

3. 在代码中配置个人Email信息，方便挂服务器的时候接收信息（或者也可以不配置...)

4. 终端/cmd cd到项目文件夹下，输入` python dailyreport.py `  ，文件夹下会出现` all_stu.json`，用于记录上报者信息，方便debug、重复使用一些信息之类的。

5. 终端会打印以下信息，`done ` 就说明上报成功，`failed`说明出现了上报内容错误，`retry`说明遇到了429问题，正在重新登录（等待120秒），其他的话说明...出了大问题

    ``` bash
    获取cookie
    stu_1.txt login succeed!
    张三 done
    ```
    
6. 假如仅仅想测试是否能成功登录和取地址，请把`manage.run()`注释掉，然后把`manage.check()`的注释符号去掉，假如配置好了发送邮件，那么需要把`manage.send()`注释符去掉。

    ```python
    if __name__ == '__main__':
        if os.path.exists('all_stu.json'):
            all_stu = json.load(open('all_stu.json', 'r'))
        else:
            all_stu = make_json("students")
        all_stu = update_json('students', all_stu)
        manage = Manager(all_stu)
        # manage.check()
        manage.run()
        # manage.send()
        if len(manage.failed) != 0:
            json.dump([i.stu_dic for i in manage.failed], open(
                'all_stu_failed.json', 'w'), ensure_ascii=False) #记录上报没成功的人
        json.dump(all_stu, open('all_stu.json', 'w'), ensure_ascii=False)
    
    ```



## 注意事项

* 一报一定要**自己报过至少一天**！！ 
* 仍然在测试中，测试的人群有限，可能会有bug
* **一报还未适配留宿同学**！！！假如需求较大会做相应适配
* **两报的模板没有对除嘉定校区以外的校区做优化，需要修改内容**



## To do

* 完善两报，使得两报功能适合所有校区
* 休眠机制完善，尽可能少地触发429错误





## 感谢

再次感谢@BlueFisher和其他contributors，也请大家给我一个star。

