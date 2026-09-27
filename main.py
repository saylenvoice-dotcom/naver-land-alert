import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 감시할 아파트 단지 목록 (매매 매물 대상)
COMPLEXES = [
    {"id": "1032", "name": "벽산늘푸른"},
    {"id": "853", "name": "염창동금호타운"},
    {"id": "8075", "name": "한강삼성1차"}
]

SEEN_FILE = "seen_articles.json"

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")

# 네이버 차단을 방지하는 실제 브라우저 패킷 헤더 설정
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://new.land.naver.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_seen(seen_data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_data, f, ensure_ascii=False, indent=2)

def fetch_articles(complex_id):
    session = requests.Session()
    # 1차 시도: new.land 최신 웹 API
    url = f"https://new.land.naver.com/api/articles/complex/{complex_id}?realEstateType=APT:ABYG:JGC&tradeType=A1&order=date_desc&page=1"
    
    try:
        res = session.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if "articleList" in data:
                return data["articleList"]
        
        # 2차 백업 시도: mobile API
        backup_url = f"https://m.land.naver.com/complex/getComplexArticleList?hscpNo={complex_id}&tradTpCd=A1&order=date_desc"
        backup_headers = HEADERS.copy()
        backup_headers["Referer"] = "https://m.land.naver.com/"
        res_backup = session.get(backup_url, headers=backup_headers, timeout=15)
        if res_backup.status_code == 200:
            data_backup = res_backup.json()
            if "result" in data_backup and "list" in data_backup["result"]:
                return data_backup["result"]["list"]

    except Exception as e:
        print(f"오류 발생 ({complex_id}): {e}")
        
    return []

def send_email(new_items):
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("지메일 설정 값이 없습니다.")
        return

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = f"🏠 [네이버 부동산] 신규 매매 매물 {len(new_items)}건 등록!"

    body = "<h2>🏠 신규 등록된 매매 매물 목록</h2><br>"
    for item in new_items:
        article_no = item.get('articleNo') or item.get('atclNo')
        article_name = item.get('articleName') or item.get('atclNm') or item['complex_name']
        building_name = item.get('buildingName') or ""
        deal_price = item.get('dealOrWarrantPrc') or item.get('prc') or "가격 정보 없음"
        floor_info = item.get('floorInfo') or item.get('flrInfo') or ""
        spc1 = item.get('area1') or item.get('spc1') or ""
        spc2 = item.get('area2') or item.get('spc2') or ""
        feature = item.get('articleFeatureDesc') or item.get('atclFtrDesc') or "-"

        body += f"""
        <div style="border:1px solid #ddd; padding:15px; margin-bottom:15px; border-radius:8px;">
            <h3 style="margin:0 0 10px 0; color:#1a73e8;">[{item['complex_name']}] {article_name} ({building_name}동)</h3>
            <p style="margin:5px 0;"><b>매매가:</b> <span style="color:#d93025; font-weight:bold; font-size:16px;">{deal_price}</span></p>
            <p style="margin:5px 0;"><b>층/총층:</b> {floor_info}</p>
            <p style="margin:5px 0;"><b>면적:</b> 공급 {spc1}㎡ / 전용 {spc2}㎡</p>
            <p style="margin:5px 0;"><b>특징:</b> {feature}</p>
            <p style="margin-top:10px;"><a href="https://m.land.naver.com/article/info/{article_no}" target="_blank" style="display:inline-block; padding:8px 15px; background-color:#03cf5d; color:white; text-decoration:none; border-radius:4px; font-weight:bold;">네이버 부동산 매물 바로가기</a></p>
        </div>
        """

    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()
        print("성공적으로 이메일을 발송했습니다!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def main():
    seen = load_seen()
    new_listings = []

    for comp in COMPLEXES:
        cid = comp["id"]
        cname = comp["name"]
        if cid not in seen:
            seen[cid] = []

        articles = fetch_articles(cid)
        for a in articles:
            ano = str(a.get("articleNo") or a.get("atclNo"))
            if ano and ano not in seen[cid]:
                seen[cid].append(ano)
                a["complex_name"] = cname
                new_listings.append(a)

    if new_listings:
        print(f"새로운 매물 {len(new_listings)}건을 발견했습니다!")
        send_email(new_listings)
    else:
        print("새로운 매물이 없습니다.")

    save_seen(seen)

if __name__ == "__main__":
    main()
