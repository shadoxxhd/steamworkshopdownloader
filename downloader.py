import subprocess
import tkinter as tk
import re
import requests
import configparser
import os
import shutil
import math
from zipfile import ZipFile
from io import BytesIO
from sys import platform
from tkinter import messagebox
from webbrowser import open_new_tab

def modpath(base, appid, wid):
    return os.path.join(base,'steamapps/workshop/content/',str(appid),str(wid))

# faster download when mixing games
def getWids(text):
    download = []
    for line in text.splitlines():
        if len(line)>0:
            # check for collection
            try:
                x = requests.get(line)
            except Exception as exc:
                output.insert(tk.END,"Couldn't get workshop page for "+line +"\n")
                output.insert(tk.END,str(type(exc))+"\n")
                output.insert(tk.END,str(exc)+"\n")
                output.see(tk.END)
                output.update()
            else: 
                if re.search("SubscribeCollectionItem",x.text):
                    # collection
                    dls = re.findall(r"SubscribeCollectionItem[\( ']+(\d+)[ ',]+(\d+)'",x.text)
                    for wid, appid in dls:
                        download.append((appid,wid))
                elif re.search("ShowAddToCollection",x.text):
                    # single item
                    wid, appid = re.findall(r"ShowAddToCollection[\( ']+(\d+)[ ',]+(\d+)'",x.text)[0]
                    download.append((appid,wid))
                else:
                    output.insert(tk.END,'"'+line+'" doesn\'t look like a valid workshop item...\n')
                    output.see(tk.END)
                    output.update()
    return download

def download():
    # don't start multiple steamcmd instances
    global running
    global cfg
    global steampath
    global defaultpath
    global URLinput
    global button1
    global output
    global login
    global passw
    global lim
    
    if running:
        return
    button1.state = tk.DISABLED
    running = True
    
    try:
        # check if steamcmd exists
        if platform == 'win32' and not os.path.exists(os.path.join(steampath,"steamcmd.exe")):
            output.insert(tk.END,"Installing steamcmd ...")
            output.see(tk.END)
            output.update()
            
            # get it from steam servers
            resp = requests.get("https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip")
            ZipFile(BytesIO(resp.content)).extractall(steampath)
            output.insert(tk.END," DONE\n")
            output.see(tk.END)
            output.update()
        # Linux SteamCMD installation process will differ too much
        # on different distributions to automate this process in one script.
        elif platform == 'linux' and shutil.which('steamcmd') is None:
            response_link = "https://developer.valvesoftware.com/wiki/SteamCMD#Linux"
            response = messagebox.askokcancel("Error", 
            "SteamCMD not detected. Detailed instructions on how to "
            "set it up on your distribution can be found here:\n" + response_link +
            "\nOpen the link in browser?")
            if response:
                open_new_tab(response_link)
            exit()
        
        
        # get array of IDs
        download = getWids(URLinput.get("1.0",tk.END))
        l = len(download)
        
        for i in range(math.ceil(l/lim)):
        #for appid in download:
            batch = download[i*lim:min((i+1)*lim,l)]
            
            # assemble command line
            if platform == 'win32':
                args = [os.path.join(steampath,'steamcmd.exe')]
            elif platform == 'linux':
                args = ['steamcmd']
            if login is not None and passw is not None:
                args.append('+login '+login+' '+passw)
            else:
                args.append('+login anonymous')
            for appid, wid in batch:
                args.append(f'+workshop_download_item {appid} {int(wid)}')
            args.append("+quit")
            
            # call steamcmd
            if platform == 'win32':
                process = subprocess.Popen(args, stdout=subprocess.PIPE, errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
            elif platform == 'linux':
                process = subprocess.Popen(args, stdout=subprocess.PIPE, errors='ignore')

            # show output
            while True:
                out = process.stdout.readline()
                #print(out.strip())
                if m := re.search("Redirecting stderr to",out):
                    output.insert(tk.END,out[:m.span()[0]]+"\n")
                    if platform == 'win32':
                        break
                if re.match("-- type 'quit' to exit --",out):
                    continue
                output.insert(tk.END,out)
                output.see(tk.END)
                output.update()
                return_code = process.poll()
                if return_code is not None:
                    for out in process.stdout.readlines():
                        #print(out.strip())
                        output.insert(tk.END,out)
                    output.see(tk.END)
                    output.update()
                    break
                
            # move mods
            pc = {} # path cache
            for appid, wid in batch:
                if appid in pc or cfg.get(str(appid),'path',fallback=None) or defaultpath:
                    path = pc.get(appid,cfg.get(str(appid),'path',
                                    fallback = os.path.join(defaultpath,str(appid))))
                    if os.path.exists(modpath(steampath,appid,wid)):
                        # download was successful
                        output.insert(tk.END, "Moving "+str(wid)+" ...")
                        output.see(tk.END)
                        output.update()
                        if(os.path.exists(os.path.join(path,str(wid)))):
                            # already exists -> delete old version
                            shutil.rmtree(os.path.join(path,str(wid)))
                        shutil.move(modpath(steampath,appid,wid),os.path.expanduser(os.path.join(path,str(wid))))
                        output.insert(tk.END, " DONE\n")
                        output.see(tk.END)
                        output.update()
                    pc[appid]=path
        # reset state
        URLinput.delete("1.0", tk.END)
    except Exception as ex:
        output.insert(tk.END,type(ex))
        output.insert(tk.END,ex)
        output.see(tk.END)
        output.update()
    finally:
        button1.state = tk.NORMAL
        running = False


def main():
    global cfg
    global steampath
    global defaultpath
    global login
    global passw
    global button1
    global URLinput
    global output
    global running
    global lim
    running = False
    
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read('downloader.ini')
    # validate ini
    if platform == 'win32' and 'general' not in cfg:
        cfg['general']={'theme': 'default', 'steampath': 'steamcmd', 'batchsize': '50'}
    elif platform == 'linux' and 'general' not in cfg:
        cfg['general']={'theme': 'default', 'steampath': "~/.local/share/Steam", 'batchsize': '50'}
    else:
        if 'theme' not in cfg['general']:
            cfg['general']['theme'] = 'default'
        if platform == 'win32' and 'steampath' not in cfg['general']:
            cfg['general']['steampath'] = 'steamcmd'
        elif platform == 'linux' and 'steampath' not in cfg['general']:
            cfg['general']['steampath'] = "~/.local/share/Steam"
        if 'lim' not in cfg['general']:
            cfg['general']['batchsize'] = '50'
    
    # set globals
    steampath = os.path.expanduser(cfg['general']['steampath'])
    defaultpath = cfg.get('general','defaultpath',fallback=None)
    if defaultpath:
        defaultpath = os.path.expanduser(defaultpath)
    theme = cfg['general']['theme']
    lim = int(cfg['general']['batchsize'])
    login = None
    passw = None
    if 'login' in cfg['general']:
        login = cfg['general']['login']
        if 'passw' in cfg['general']:
            passw = cfg['general']['passw']
    
    padx = 7
    pady = 4
    
    if theme=='sdark':
        # Solarized dark
        bg1="#002b36"
        bg2="#073642"
        textcol="#b58900"
    elif theme=='solar':
        # Solarized
        bg1="#fdf6e3"
        bg2="#eee8d5"
        textcol="#073642"
    elif theme=='black':
        bg1="#333"
        bg2="#555"
        textcol="#eee"
    elif theme=='white':
        bg1="#e8e8e8"
        bg2="#e8e8e8" 
        textcol="#000000"
        pass
    elif theme=='default':
        bg1=None
        bg2=None
        textcol=None
    else:
        print("invalid theme specified")
        bg1=None
        bg2=None
        textcol=None
    
    # create UI            
    root = tk.Tk()
    root['bg'] = bg1
    root.title("Steam Workshop Downloader")
    
    frame = tk.Frame(root, bg=bg1)
    frame.pack(padx=0,pady=0,side=tk.LEFT, fill=tk.Y)
    
    #canvas1 = tk.Canvas(root, width = 820, height = 300)
    #canvas1.pack()
    
    #textAppid = tk.Text(root, width = 30, height = 1)
    #canvas1.create_window(250,50,window=textAppid)
    
    #labelAppid = tk.Label(root, text='App ID')
    #canvas1.create_window(50,50,window=labelAppid)
    
    labelURLi = tk.Label(frame, text='Workshop URLs', fg=textcol, bg=bg1)
    #canvas1.create_window(50,140,window=labelURLi)
    labelURLi.pack(padx=padx,pady=pady,side=tk.TOP)
    
    URLinput = tk.Text(frame, width = 67, height = 20, fg=textcol, bg=bg2) # root
    #canvas1.create_window(250,140,window=URLinput)
    URLinput.pack(padx=padx,pady=pady,side=tk.TOP, expand=1, fill=tk.Y)
    URLinput.bind("<Button-3>", lambda a: URLinput.insert(tk.END,root.clipboard_get()+"\n"))
    
    button1 = tk.Button(frame, text='Download', command=download, fg=textcol, bg=bg1) # root
    #canvas1.create_window(250,270,window=button1)
    button1.pack(padx=padx,pady=pady,side=tk.BOTTOM, fill=tk.X)
    
    output = tk.Text(root, width=56, height = 20, fg=textcol, bg=button1['bg'], font=("Consolas",10))
    #canvas1.create_window(600,150,window=output)
    output.pack(padx=padx,pady=pady,side=tk.RIGHT,fill=tk.BOTH,expand=1)
    
    root.mainloop()
    
    if not os.path.exists('downloader.ini'): # remove this when in-app options menu exists
        with open('downloader.ini', 'w') as file:
            cfg.write(file)

if __name__ == '__main__':
    main()
