import subprocess
import tkinter as tk
import re
import requests

## TODO
# manage login, move (& rename?) downloads


global textAppid
global textWIDs
global output
global button1
global running
global cfg
running = False

def getWids(text):
    download = {}
    for line in text.splitlines():
        # check for collection
        x = requests.get(line)
        if re.search("SubscribeCollectionItem",x.text):
            # collection
            dls = re.findall(r"SubscribeCollectionItem[\( ']+(\d+)[ ',]+(\d+)'",x.text)
            for wid, appid in dls:
                if appid not in download:
                    download[appid] = []
                download[appid].append(wid)
        else:
            wid, appid = re.findall(r"ShowAddToCollection[\( ']+(\d+)[ ',]+(\d+)'",x.text)[0]
            if appid not in download:
                download[appid] = []
            download[appid].append(wid)
    return download


def download():
    # don't start multiple steamcmd instances
    global running
    if running:
        return
    #button1.state = 'disabled'
    running = True
    
    # get array of IDs
    global textWIDs
    download = getWids(textWIDs.get("1.0",tk.END))
    
    for appid in download:
        # assemble command line
        args = ['steamcmd/steamcmd.exe','+login anonymous']
        for wid in download[appid]:
            args.append(f'+workshop_download_item {appid} {int(wid)}')
        args.append("+quit")
        
        # call steamcmd
        process = subprocess.Popen(args, stdout=subprocess.PIPE, errors='ignore')
    
        # show output
        global output
        while True:
            out = process.stdout.readline()
            #print(out.strip())
            output.insert(tk.END,out)
            output.update()
            return_code = process.poll()
            if return_code is not None:
                for out in process.stdout.readlines():
                    #print(out.strip())
                    output.insert(tk.END,out)
                break

    # reset state
    textWIDs.delete("1.0", tk.END)
    button1.state = "normal"
    running = False


# MAIN

# create UI            
root = tk.Tk()
    
canvas1 = tk.Canvas(root, width = 820, height = 300)
canvas1.pack()
    
#textAppid = tk.Text(root, width = 30, height = 1)
#canvas1.create_window(250,50,window=textAppid)

#labelAppid = tk.Label(root, text='App ID')
#canvas1.create_window(50,50,window=labelAppid)

textWIDs = tk.Text(root, width = 30, height = 13)
canvas1.create_window(250,140,window=textWIDs)

labelWIDs = tk.Label(root, text='Workshop URLs')
canvas1.create_window(50,140,window=labelWIDs)

button1 = tk.Button(text='Download', command=download)
canvas1.create_window(250,270,window=button1)

output = tk.Text(root, width=50, height = 15)
canvas1.create_window(600,150,window=output)

root.mainloop()