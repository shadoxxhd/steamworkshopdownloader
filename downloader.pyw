import subprocess
import tkinter as tk
import re
import requests
import configparser
import os
import shutil
import math
import time
from zipfile import ZipFile
from io import BytesIO

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
                log("Couldn't get workshop page for "+line)
                log(type(exc))
                log(exc)
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
                    log('"'+line+'" doesn\'t look like a valid workshop item...\n')
    return download

def log(data, newline = True, update = True):
    global output
    output.config(state='normal')
    output.insert(tk.END,str(data)+("\n" if newline else ""))
    output.config(state='disabled')
    if(update):
        output.see(tk.END)
        output.update()

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
    global steamguard
    global SGinput
    global lim
    global showConsole
    
    if running:
        return
    button1.state = tk.DISABLED
    running = True
    
    try:
        # check if steamcmd exists
        if not os.path.exists(os.path.join(steampath,"steamcmd.exe")):
            log("Installing steamcmd ...",0)
            
            # get it from steam servers
            resp = requests.get("https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip")
            ZipFile(BytesIO(resp.content)).extractall(steampath)
            log(" DONE")
        
        # get array of IDs
        download = getWids(URLinput.get("1.0",tk.END))
        l = len(download)
        sgcode = None
        if steamguard:
            sgcode = SGinput.get()

        errors = {}
        
        for i in range(math.ceil(l/lim)):
        #for appid in download:
            batch = download[i*lim:min((i+1)*lim,l)]
            
            # assemble command line
            args = [os.path.join(steampath,'steamcmd.exe')]
            if login is not None and passw is not None:
                args.append('+login '+login+' '+passw+(' '+sgcode if steamguard else ''))
            elif login is not None:
                args.append('+login '+login)
            else:
                args.append('+login anonymous')
            for appid, wid in batch:
                args.append(f'+workshop_download_item {appid} {int(wid)}')
            args.append("+quit")
            
            # call steamcmd
            if showConsole:
                process = subprocess.Popen(args, stdout=None, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                process = subprocess.Popen(args, stdout=subprocess.PIPE, errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
        
            # show output
            while True:
                if showConsole:
                    time.sleep(1)
                    if process.poll() is not None:
                        break
                    continue
                out = process.stdout.readline()
                if m := re.search("Redirecting stderr to",out):
                    log(out[:m.span()[0]],1,0)
                    break
                if re.match("-- type 'quit' to exit --",out):
                    continue
                log(out)
                return_code = process.poll()
                if return_code is not None:
                    for out in process.stdout.readlines():
                        log(out,0,0)
                    log("",0)
                    if return_code == 0:
                        # todo: check for individual status
                        pass
                    else:
                        for wid in batch:
                            errors[wid]=1
                    break
                
            # move mods
            pc = {} # path cache
            for appid, wid in batch:
                if appid in pc or cfg.get(str(appid),'path',fallback=None) or defaultpath:
                    path = pc.get(appid,cfg.get(str(appid),'path',
                                    fallback = defaultpath and os.path.join(defaultpath,str(appid))))
                    if os.path.exists(modpath(steampath,appid,wid)):
                        # download was successful
                        log("Moving "+str(wid)+" ...",0,0)
                        if(os.path.exists(os.path.join(path,str(wid)))):
                            # already exists -> delete old version
                            shutil.rmtree(os.path.join(path,str(wid)))
                        shutil.move(modpath(steampath,appid,wid),os.path.join(path,str(wid)))
                        log(" DONE")
                    pc[appid]=path
        # reset state
        if(len(errors)==0): # don't reset input if steamcmd crashed; todo: check individual items
            URLinput.delete("1.0", tk.END)
    except Exception as ex:
        log(type(ex))
        log(ex)
    finally:
        button1.state = tk.NORMAL
        running = False


def main():
    global cfg
    global steampath
    global defaultpath
    global login
    global passw
    global steamguard
    global button1
    global URLinput
    global output
    global SGinput
    global running
    global lim
    global showConsole
    running = False
    
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read('downloader.ini')
    # validate ini
    if 'general' not in cfg:
        cfg['general']={'theme': 'default', 'steampath': 'steamcmd', 'batchsize': '50', 'showConsole': 'no', 'defaultpath': 'mods'}
    else:
        if 'theme' not in cfg['general']:
            cfg['general']['theme'] = 'default'
        if 'steampath' not in cfg['general']:
            cfg['general']['steampath'] = 'steamcmd'
        if 'lim' not in cfg['general']:
            cfg['general']['batchsize'] = '50'
        if 'showConsole' not in cfg['general']:
            cfg['general']['showConsole'] = 'no'
    
    # set globals
    steampath = cfg['general']['steampath']
    defaultpath = cfg.get('general','defaultpath',fallback=None)
    theme = cfg['general']['theme']
    lim = cfg.getint('general','batchsize')
    login = None
    passw = None
    steamguard = None
    if 'login' in cfg['general']:
        login = cfg['general']['login']
        if 'passw' in cfg['general']:
            passw = cfg['general']['passw']
        if 'steamguard' in cfg['general']:
            steamguard = cfg.getboolean('general','steamguard')
        else:
            cfg['general']['steamguard'] = "no"

    showConsole = cfg.getboolean('general','showConsole')
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
    
    labelURLi = tk.Label(frame, text='Workshop URLs', fg=textcol, bg=bg1)
    labelURLi.pack(padx=padx,pady=pady,side=tk.TOP)
    
    URLinput = tk.Text(frame, width = 67, height = 20, fg=textcol, bg=bg2) # root
    URLinput.pack(padx=padx,pady=pady,side=tk.TOP, expand=1, fill=tk.Y)
    URLinput.bind("<Button-3>", lambda a: URLinput.insert(tk.END,root.clipboard_get()+"\n"))
    
    button1 = tk.Button(frame, text='Download', command=download, fg=textcol, bg=bg1) # root
    button1.pack(padx=padx,pady=pady,side=tk.LEFT, fill=tk.X, expand=1)

    output = tk.Text(root, width=56, height = 20, fg=textcol, bg=button1['bg'], font=("Consolas",10), state="disabled")
    output.pack(padx=padx,pady=pady,side=tk.BOTTOM,fill=tk.BOTH,expand=1)

    if(steamguard):
        SGlabel = tk.Label(root, text="SteamGuard Code", fg=textcol, bg=bg1)
        SGlabel.pack(padx=padx, pady=pady, side=tk.LEFT, expand=0, fill=tk.X)

        SGinput = tk.Entry(root, width=5, fg=textcol,bg=bg2)
        SGinput.pack(padx=padx, pady=pady, side=tk.LEFT, expand=1, fill=tk.X)
    
    root.mainloop()
    
    if not os.path.exists('downloader.ini'): # remove this when in-app options menu exists
        with open('downloader.ini', 'w') as file:
            cfg.write(file)

if __name__ == '__main__':
    main()