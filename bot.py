
# 新王者之劍 Granado Espada M - DC 組隊 Bot
# Python 3.10+ / discord.py 2.3+
# 指令: /開團 /報名 /名單 /出戰 /提醒 /取消報名 /刪除團
import discord, json, os, asyncio

# --- Render 免費 Web Service 需要一個會回應的 Port，不然它會以為 Bot 死掉 ---
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os as _os
class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot is alive")
    def log_message(self, *a): pass
def _run_web():
    try:
        HTTPServer(("0.0.0.0", int(_os.getenv("PORT", "10000"))), _H).serve_forever()
    except Exception as e:
        print("web server:", e)
threading.Thread(target=_run_web, daemon=True).start()
# --- 假 Web 伺服器結束 ---


from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from pathlib import Path

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = Path("ge_teams.json")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"teams": {}}
def save(d):
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

# 定位顏色對應
ROLE_EMOJI = {"坦克":"🛡️","輸出":"⚔️","輔助":"💚","控場":"🌀"}

@bot.event
async def on_ready():
    print(f"✅ 已上線: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ 已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print("同步失敗:", e)
    check_reminder.start()

# ---------- /開團 ----------
@bot.tree.command(name="開團", description="建立一場新王者之劍組隊")
@app_commands.describe(副本="例如: 討伐戰 / 遠征副本 / 公會戰 / 領地戰", 日期="例如: 11/22", 集合時間="例如: 20:00", 開打時間="例如: 20:30", 語音頻道="例如: 語音-一團")
async def 開團(interaction: discord.Interaction, 副本: str, 日期: str, 集合時間: str, 開打時間: str = "20:30", 語音頻道: str = "未指定"):
    d = load()
    gid = str(interaction.guild_id)
    team_id = f"{gid}_{副本}_{日期}"
    d["teams"][team_id] = {"副本":副本,"日期":日期,"集合":集合時間,"開打":開打時間,"語音":語音頻道,"團長":interaction.user.display_name,"頻道":interaction.channel_id,"成員":{},"出戰":{}}
    save(d)
    embed = discord.Embed(title=f"⚔️ 新王者之劍 - {副本} 開團！", color=0xE8B84B)
    embed.add_field(name="📅 日期", value=日期, inline=True)
    embed.add_field(name="🕗 集合", value=集合時間, inline=True)
    embed.add_field(name="⚔️ 開打", value=開打時間, inline=True)
    embed.add_field(name="🎙️ 語音", value=語音頻道, inline=False)
    embed.add_field(name="👑 團長", value=interaction.user.mention, inline=True)
    embed.add_field(name="📝 報名方式", value="打 `/報名` 填你的 3 隻角色\n打 `/名單` 看目前報名", inline=False)
    embed.set_footer(text=f"團ID: {team_id} | 請團長記下，之後指定出戰要用")
    await interaction.response.send_message(embed=embed)

# ---------- /報名 ----------
@bot.tree.command(name="報名", description="報名參加，填你 3 隻角色 (MCC 一人帶3隻)")
@app_commands.describe(副本="要報哪個副本", 日期="例如: 11/22", 角色1="例如: 雷提夫-坦克", 角色2="例如: 蒂卡妮兒-輸出", 角色3="例如: 巴哈-輸出", 狀態="可參加 / 晚到 / 候補", 備註="例如: 只能打到22:00")
@app_commands.choices(狀態=[app_commands.Choice(name="可參加", value="可參加"), app_commands.Choice(name="晚到", value="晚到"), app_commands.Choice(name="候補", value="候補")])
async def 報名(interaction: discord.Interaction, 副本: str, 日期: str, 角色1: str, 角色2: str, 角色3: str, 狀態: app_commands.Choice[str] = None, 備註: str = ""):
    d = load()
    gid = str(interaction.guild_id)
    team_id = f"{gid}_{副本}_{日期}"
    if team_id not in d["teams"]:
        await interaction.response.send_message(f"❌ 找不到 {副本} {日期} 的團，請先請團長打 `/開團`", ephemeral=True); return
    status = 狀態.value if 狀態 else "可參加"
    d["teams"][team_id]["成員"][str(interaction.user.id)] = {"dc":interaction.user.display_name,"mention":interaction.user.mention,"角色":[角色1,角色2,角色3],"狀態":status,"備註":備註}
    save(d)
    await interaction.response.send_message(f"✅ {interaction.user.mention} 報名成功！\n**{副本} {日期}** - {status}\n角色1: {角色1}\n角色2: {角色2}\n角色3: {角色3}\n備註: {備註 or '無'}")

# ---------- /名單 ----------
@bot.tree.command(name="名單", description="查看目前報名名單")
@app_commands.describe(副本="例如: 討伐戰", 日期="例如: 11/22")
async def 名單(interaction: discord.Interaction, 副本: str, 日期: str):
    d = load()
    team_id = f"{str(interaction.guild_id)}_{副本}_{日期}"
    t = d["teams"].get(team_id)
    if not t:
        await interaction.response.send_message("❌ 找不到這團", ephemeral=True); return
    lines = []
    counts = {"坦克":0,"輸出":0,"輔助":0,"控場":0}
    for m in t["成員"].values():
        roles = " | ".join(m["角色"])
        for r in ["坦克","輸出","輔助","控場"]:
            if r in roles: counts[r]+=roles.count(r)
        lines.append(f"• **{m['dc']}** [{m['狀態']}] {roles} {(' - '+m['備註']) if m['備註'] else ''}")
    embed = discord.Embed(title=f"📋 {副本} {日期} - 報名名單 ({len(t['成員'])}人)", description="\n".join(lines) if lines else "還沒人報名，快來當第一個！", color=0x2B2D31)
    embed.add_field(name="📊 定位統計", value=f"🛡️ 坦克 {counts['坦克']} | ⚔️ 輸出 {counts['輸出']} | 💚 輔助 {counts['輔助']} | 🌀 控場 {counts['控場']}", inline=False)
    embed.add_field(name="🕗 集合 / 開打", value=f"{t['集合']} / {t['開打']} | 🎙️ {t['語音']}", inline=False)
    await interaction.response.send_message(embed=embed)

# ---------- /出戰 ----------
@bot.tree.command(name="出戰", description="團長指定出戰成員 (用 @提及)")
@app_commands.describe(副本="例如: 討伐戰", 日期="例如: 11/22", 成員="選一位已報名的成員", 本場主用角色="從他報名的3隻中選一隻填入")
async def 出戰(interaction: discord.Interaction, 副本: str, 日期: str, 成員: discord.Member, 本場主用角色: str):
    d = load()
    team_id = f"{str(interaction.guild_id)}_{副本}_{日期}"
    t = d["teams"].get(team_id)
    if not t or str(成員.id) not in t["成員"]:
        await interaction.response.send_message("❌ 這個人還沒報名，請他先打 /報名", ephemeral=True); return
    t["出戰"][str(成員.id)] = {"dc":成員.display_name,"主用":本場主用角色}
    save(d)
    # 顯示完整出戰名單
    lst = "\n".join([f"• **{v['dc']}** - 主用: {v['主用']}" for v in t["出戰"].values()])
    await interaction.response.send_message(f"✅ 已加入出戰！\n**{副本} {日期} 出戰名單 ({len(t['出戰'])}人)**\n{lst}")

# ---------- /提醒 ----------
@bot.tree.command(name="提醒", description="手動發集合提醒到這個頻道")
@app_commands.describe(副本="例如: 討伐戰", 日期="例如: 11/22", 幾分鐘後="例如: 30")
async def 提醒(interaction: discord.Interaction, 副本: str, 日期: str, 幾分鐘後: int = 30):
    d = load()
    team_id = f"{str(interaction.guild_id)}_{副本}_{日期}"
    t = d["teams"].get(team_id)
    if not t:
        await interaction.response.send_message("❌ 找不到這團", ephemeral=True); return
    mentions = " ".join([f"<@{k}>" for k in t["成員"].keys()]) or "@everyone"
    await interaction.response.send_message(f"@everyone ⚔️ **集合提醒！**\n**{副本} {日期}** {幾分鐘後}分鐘後集合！\n🕗 集合: {t['集合']} | ⚔️ 開打: {t['開打']}\n🎙️ 語音: {t['語音']}\n{mentions}\n請上線集合！")

# ---------- /取消報名 ----------
@bot.tree.command(name="取消報名", description="取消你的報名")
@app_commands.describe(副本="例如: 討伐戰", 日期="例如: 11/22")
async def 取消報名(interaction: discord.Interaction, 副本: str, 日期: str):
    d = load()
    team_id = f"{str(interaction.guild_id)}_{副本}_{日期}"
    if team_id in d["teams"] and str(interaction.user.id) in d["teams"][team_id]["成員"]:
        del d["teams"][team_id]["成員"][str(interaction.user.id)]
        save(d)
        await interaction.response.send_message(f"✅ {interaction.user.mention} 已取消報名", ephemeral=True)
    else:
        await interaction.response.send_message("❌ 你沒有報名這團", ephemeral=True)

@tasks.loop(minutes=1)
async def check_reminder():
    pass # 手動 /提醒 已足夠，自動提醒可之後再加定時任務

if __name__ == "__main__":
    if not TOKEN:
        print("❌ 請設定環境變數 DISCORD_TOKEN")
    else:
        bot.run(TOKEN)
