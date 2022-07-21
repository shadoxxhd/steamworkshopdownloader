import subprocess
import tkinter as tk
import re
import requests
import configparser
import os
import shutil
import math
import logging
from zipfile import ZipFile
from io import BytesIO
from sys import platform
from tkinter import messagebox
from webbrowser import open_new_tab


# Source: gist.github.com/moshekaplan/c425f861de7bbf28ef06
class TextHandler(logging.Handler):
    """This class allows you to log to a Tkinter Text or ScrolledText widget"""
    def __init__(self, text):
        # run the regular Handler __init__
        logging.Handler.__init__(self)
        # Store a reference to the Text it will log to
        self.text = text

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text.configure(state='normal')
            self.text.insert(tk.END, msg + '\n')
            self.text.configure(state='disabled')
            # Autoscroll to the bottom
            self.text.yview(tk.END)
        # This is necessary because we can't modify the Text from other threads
        self.text.after(0, append)


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
                logger.error(f"Couldn't get workshop page for {line}")
                #output.insert(tk.END,"Couldn't get workshop page for "+line +"\n")
                logger.error(str(type(exc)))
                #output.insert(tk.END,str(type(exc))+"\n")
                logger.error(str(exc))
                #output.insert(tk.END,str(exc)+"\n")
                #output.see(tk.END)
                #output.update()
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
                    logger.error(f'"{line}" doesn\'t look like a valid workshop item...')
                    #output.insert(tk.END,'"'+line+'" doesn\'t look like a valid workshop item...\n')
                    #output.see(tk.END)
                    #output.update()
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
    global logger
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
            logger.debug("Platform recognized as Windows")
            logger.info("Installing steamcmd ...")
            #output.insert(tk.END,"Installing steamcmd ...")
            #output.see(tk.END)
            #output.update()
            
            # get it from steam servers
            resp = requests.get("https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip")
            ZipFile(BytesIO(resp.content)).extractall(steampath)
            logger.info("steamcmd installed.")
            #output.insert(tk.END," DONE\n")
            #output.see(tk.END)
            #output.update()
        # Linux SteamCMD installation process will differ too much
        # on different distributions to automate this process in one script.
        elif platform == 'linux' and not os.path.exists("/usr/bin/steamcmd") and shutil.which('steamcmd') is None:
            logger.debug("Platform recognized as Linux")
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
            logger.debug(' '.join(args))
            
            logger.debug("steamcmd log start")
            # call steamcmd
            if platform == 'win32':
                process = subprocess.Popen(args, stdout=subprocess.PIPE, errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
            elif platform == 'linux':
                process = subprocess.Popen(args, stdout=subprocess.PIPE, errors='ignore')

            # show output
            while True:
                out = process.stdout.readline()
                if m := re.search("Redirecting stderr to",out):
                    logger.info(out[:m.span()[0]])
                    output.insert(tk.END,out[:m.span()[0]]+"\n")
                    if platform == 'win32':
                        break
                if re.match("-- type 'quit' to exit --",out):
                    continue
                logger.info(out.strip('\n'))
                #output.insert(tk.END,out)
                #output.see(tk.END)
                #output.update()
                return_code = process.poll()
                if return_code:
                    for out in process.stdout.readlines():
                        logger.info(out.strip())
                        #output.insert(tk.END,out)
                    #output.see(tk.END)
                    #output.update()
                    break
            logger.debug("steamcmd log stop")
                
            # move mods
            pc = {} # path cache
            for appid, wid in batch:
                if appid in pc or cfg.get(str(appid),'path',fallback=None) or defaultpath:
                    path = pc.get(appid,cfg.get(str(appid),'path',
                                    fallback = os.path.join(defaultpath,str(appid))))
                    if os.path.exists(modpath(steampath,appid,wid)):
                        # download was successful
                        logger.info(f"Moving item {str(wid)} ...")
                        #output.insert(tk.END, "Moving "+str(wid)+" ...")
                        #output.see(tk.END)
                        #output.update()
                        if(os.path.exists(os.path.join(path,str(wid)))):
                            # already exists -> delete old version
                            shutil.rmtree(os.path.join(path,str(wid)))
                        logger.debug(f"from {modpath(steampath,appid,wid)}")
                        logger.debug(f"to {os.path.expanduser(os.path.join(path,str(wid)))}")
                        # Fixed the part where it duplicated the mod ID in destination path
                        shutil.move(modpath(steampath,appid,wid), os.path.expanduser(path))
                        logger.info(f"Item moved.")
                        #output.insert(tk.END, " DONE\n")
                        #output.see(tk.END)
                        #output.update()
                    pc[appid]=path
        # reset state
        URLinput.delete("1.0", tk.END)
    except Exception as ex:
        logger.error(type(ex))
        logger.error(ex)
        #output.insert(tk.END,type(ex))
        #output.insert(tk.END,ex)
        #output.see(tk.END)
        #output.update()
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
    global logger
    global running
    global lim
    running = False
    
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read('downloader.ini')
    # validate ini
    if 'general' not in cfg:
        cfg['general']={'theme': 'default', 'steampath': 'steamcmd', 'batchsize': '50'}
    else:
        if 'theme' not in cfg['general']:
            cfg['general']['theme'] = 'default'
        if 'steampath' not in cfg['general']:
            cfg['general']['steampath'] = 'steamcmd'
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
    
    output = tk.Text(root, width=56, height = 20, fg=textcol, bg=button1['bg'], font=("Consolas",10), state='disabled')
    #canvas1.create_window(600,150,window=output)
    output.pack(padx=padx,pady=pady,side=tk.RIGHT,fill=tk.BOTH,expand=1)
    
    # Using constants to set up formatting is entirely optional
    LOG_LEVEL = logging.DEBUG
    LOG_FORMAT = '%(asctime)s,%(msecs)03d [%(levelname)s]: %(message)s'
    LOG_DATEFMT = "%H:%M:%S"
    #LOG_DATEFMT = "%Y-%m-%d %H:%M:%S" (Verbose)

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    # Instantiate handler
    text_handler = TextHandler(output)
    text_handler.setLevel(LOG_LEVEL)
    text_handler.setFormatter(formatter)

    # Add the handler to logger
    logger = logging.getLogger()
    logger.addHandler(text_handler)
    logger.setLevel(LOG_LEVEL)

    root.mainloop()
    
    if not os.path.exists('downloader.ini'): # remove this when in-app options menu exists
        with open('downloader.ini', 'w') as file:
            cfg.write(file)

if __name__ == '__main__':
    main()
