#!/home/GTSesMon/venv/bin/python
from netmiko import ConnectHandler
from datetime import datetime
import sys
import glob
import os, time
from time import gmtime, strftime
import smtplib
from email.mime.text import MIMEText
import jtextfsm as textfsm
import csv
from operator import itemgetter
import smbclient
import ftplib
import pyodbc
import os

def determine_parser(deviceTypeDB):
    if deviceTypeDB=='SIP-VIDEO':
        return "parserVideo.textfsm"
    elif deviceTypeDB=='SIP-CALL':
        return "parserSIP.textfsm"
    elif deviceTypeDB=='PRI-CALL':
        return "parserPRI.textfsm"

#upload file to //tekserv/Gargwacct/SIPGWMon
def upload(ftp, file):
    ext = os.path.splitext(file)[1]
    if ext in (".txt", ".htm", ".html"):
        ftp.storlines("STOR " + file, open(file))
    else:
        ftp.storbinary("STOR " + file, open(file, "rb"), 1024)

#Connect to
def connect_db():
    dsn = 'server'
    user = 'user'
    pwd = 'password'
    database = 'DB'
    host = 'host'
    con_string = 'DSN=%s;UID=%s;PWD=%s;' % (dsn, user, pwd)
    connection = pyodbc.connect(con_string)
    return connection

def get_gateway():
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT gateway_id, device_type, ip_text FROM T_gateway_info")
    results = cursor.fetchall()
    cursor.close()
    del cursor
    connection.close()
    return results

os.environ['TZ'] = 'Turkey'
time.tzset()
create_time = strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
gateway_info = get_gateway()
gt_counter = 0
for gateway in gateway_info:
    isConnected = False
    ip_info = gateway_info[gt_counter][2]
    cisco_router = {
        'device_type': 'cisco_ios',
        'ip': ip_info,
        'username': 'user',
        'password': 'pass',
        'secret': 'enable',
        'verbose': False,
    }

    if gateway_info[gt_counter][1] == 'CALL':
        logfile = open("/home/GTSesMon/PycharmProjects/SIPGatewayLog/siplog_1001302", "w")
    elif gateway_info[gt_counter][1] == 'VIDEO':
        logfile = open("/home/GTSesMon/PycharmProjects/SIPGatewayLog/siplog_14412", "w")

    net_connect = ConnectHandler(**cisco_router)
    prompt_text = net_connect.find_prompt()
    print(prompt_text)
    if prompt_text != '':
        net_connect.enable()
        if gateway_info[gt_counter][1]=='CALL':
            output = net_connect.send_command('sh call history voice brief | i :')
        elif gateway_info[gt_counter][1]=='VIDEO':
            output = net_connect.send_command('sh call history video brief | i :')
        logfile.write(output)
        net_connect.disconnect()
        logfile.close()
        #CALL-SIP/CALL-PRI
        #VIDEO-SIP/VIDEO-PRI
        #IP RANGE
        #OPEN TEMPLATE
        if gateway_info[gt_counter][1] == 'CALL':
            template = open("parserSIP.textfsm")
        elif gateway_info[gt_counter][1] == 'VIDEO':
            template = open("parserVideo.textfsm")
        re_table = textfsm.TextFSM(template)
        fsm_results = re_table.ParseText(output)
        gateway_id_list = [[gateway_info[gt_counter][0]]] * len(fsm_results)
        gateway_type_list = [[gateway_info[gt_counter][1]]] * len(fsm_results)
        appended_fsm_results = [x+y+z for x,y,z in zip(fsm_results,gateway_id_list,gateway_type_list)]
        outfilename = 'gwid'+str(gateway_info[gt_counter][0])+'date'+create_time+'.csv'
        outfile = open(outfilename, "w+")
        counter = 0
        for row in appended_fsm_results:
            col_counter = 0
            for s in row:
                outfile.write("%s;" % s)
                col_counter += 1
            outfile.write("\n")
            counter += 1
        print("Write %d records" % counter)
        outfile.close()
        template.close()
        ftp = ftplib.FTP("ftp_ip_add") 
        ftp.login("ftp_user", "ftp_pass") 
        ftp.cwd("SIPGWMon")
        ftpfile = open(outfilename, "rb")
        ftp.storlines("STOR " +outfilename, ftpfile)
        ftpfile.close()
        ftp.quit()
    else:
        msg = MIMEText(ip_info+" DOWN!")
        msg['Subject'] = 'SIP Gateway Monitoring Alert'
        msg['From'] = 'SIPGW@company.com.tr'
        msg['To'] = 'user@company.com.tr'
        s = smtplib.SMTP('smtpserv.fw.company.com.tr')
        s.send_message(msg)
        s.quit()
    gt_counter += 1

now = time.time()
listing = glob.glob('/home/GTSesMon/PycharmProjects/SIPGatewayLog/*.csv')
logfileLOG = glob.glob('/home/GTSesMon/siplogjobv4.log')

for list in listing:
    if os.path.isfile(list):
        if os.stat(list).st_mtime < now - 1 * 60*60*(1/2):
            os.remove(list)

for list in logfileLOG:
    if os.path.isfile(list):
        if os.stat(list).st_mtime < now - 1 * 60*60*(1/2):
            os.remove(list)