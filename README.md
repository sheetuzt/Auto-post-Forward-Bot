## 🔄 Auto Forward Bot - Features & Commands Guide

We’ve added several useful features and commands to help you control the bot better. Here's the complete list:

✅ Features & How to Use:

1. Auto Forwarding  
   Automatically forwards messages from the source chat to the target chat without the “forwarded from” tag.

2. Duplicate Prevention  
   Already forwarded messages will not be forwarded again.

3. Delay System  
   Set a custom delay (in seconds) between forwarded messages using the line no `23`  
   - Usage: setdelay `DELAY_SECONDS` = `5`

4. Status Check  
   See bot’s current status, `Active ✅`, and `inactive` ❌ `/status`.

5. 👉  All commands list 🌟 
  
       ```
         
         /login - 🔐 Account login
         /logout - 🚪 Session delete 
         /cancel - ❌ Current process stop
         Settings:
         /on | /off - ✅ Forwarding chalu/band
         /setdelay [Sec] - ⏱ Delay set karein
         /skip - 🛹 Agla message skip karein
         /resume - 🏹 Forwarding firse chalu karein

         Management:
         /addsource [ID] | /remsource [ID]
         /listsources - 📄 Sources dekhein
         /addtarget [ID] | /removetarget [ID]
         /listtargets - 🎯 Targets dekhein

         Stats:
         /count - 📊 Total messages count
         /noor - 👀 Detailed Report
         /status - ⚡ Bot status

         Owner Only:
         /addadmin [ID] - 👤 Naya admin banayein
         /ban [ID] - 🚫 User ban karein
         /unban [ID] - 😇 User unban karein
         /removeuser [ID] - 🗑 User data wipe karein
         /restart - ♻ Bot restart karein```

-----

### 🚀 Deployment  
**Set environment variables**

# ✅ Telegram API credentials
   - `API_ID`=667788990
   - `API_HASH`=wwq8325ba83751dfade998899988gh
   - `BOT_TOKEN`=enter your bot token

# 🆔 Telegram channel/chat IDs 
   - `SOURCE_CHAT_ID`=-1001234567890
   - `TARGET_CHAT_ID`=-1002888859999

# 🔗 MongoDB connection URI 
   - `MONGO_URI`=mongodb+srv://woodcraft:angellol@cluster0-&appName=Cluster0

# 👤 Bot admin user IDs (comma-separated if multiple) 
   - `DEFAULT_ADMINS`=123456789
  
# 🌄 Image URLs (can be used in bot responses) 
   - `STATUS_URL`=https://i.imgur.com/1ARGsWp.png
   - `WOODCRAFT_URL`=https://i.imgur.com/1ARGsWp.png
   - `NOOR_URL`=https://i.imgur.com/E5zwKTY.png

# 🚀 Server port 
   - `PORT`=8080


## 🌐 Web Interface:
A small Flask server is running in the background. If you open the hosted URL, you’ll see:  
## 🤖 Activate the MY bot!

`Need more help? Just message the Repo Owner.` MYBOTS

-----
## 💥 Credits: [𝐖𝐎𝐎𝐃𝐜𝐫𝐚𝐟𝐭](https://t.me/mybots23)


## 📅 Last Update 🔄 On: `14/02/2026`
