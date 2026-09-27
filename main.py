import os
import json
import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

COMPLEXES = [
    {"id": "1032", "name": "벽산늘푸른"},
    {"id": "853", "name": "염창동금호타운"},
    {"id": "8075", "name": "한강삼성1차"}
]

SEEN_FILE = "seen_articles.json"

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"seen 파일 읽기 예외 발생: {e}")
            return {}
    return {}

def save_seen(seen_data):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"seen 파일 저장 예외 발생: {e}")

def fetch_articles(complex_id):
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Referer": f"https://new.land.naver.com/complexes/{complex_id}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    url = f"https://new.land.naver.com/api/articles/complex/{complex_id}?realEstateType=APT:ABYG:JGC&tradeType=A1&order=date_desc&page=1"

    try:
        res = session.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            try:
                data = res.json()
                if "articleList" in data:
                    return data["articleList"]
            except Exception:
                print(f"[{complex_id}] 네이버 응답이 JSON 형식이 아닙니다 (차단 가능성).")
        else:
            print(f"[{complex_id}] HTTP 응답 에러 코드: {res.status_code}")
    except Exception as e:
        print(f"[{complex_id}] 네트워크 요청 실패: {e}")

    return []

def send_email(new_items):
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("지메일 설정 값(Secrets)이 없습니다.")
        return

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = f"🏠 [네이버 부동산] 신규 매매 매물 {len(new_items)}건 등록!"

    body = "<h2>🏠 신규 등록된 매매 매물 목록</h2><br>"
    for item in new_items:
        ano = item.get('articleNo') or item.get('atclNo')
        aname = item.get('articleName') or item.get('atclNm') or item['complex_name']
        bname = item.get('buildingName') or ""
        prc = item.get('dealOrWarrantPrc') or item.get('prc') or "가격 정보 없음"
        flr = item.get('floorInfo') or item.get('flrInfo') or ""
        s1 = item.get('area1') or item.get('spc1') or ""
        s2 = item.get('area2') or item.get('spc2') or ""
        ftr = item.get('articleFeatureDesc') or item.get('atclFtrDesc') or "-"

        body += f"""
        <div style="border:1px solid #ddd; padding:15px; margin-bottom:15px; border-radius:8px;">
            <h3 style="margin:0 0 10px 0; color:#1a73e8;">[{item['complex_name']}] {aname} ({bname}동)</h3>
            <p style="margin:5px 0;"><b>매매가:</b> <span style="color:#d93025; font-weight:bold; font-size:16px;">{prc}</span></p>
            <p style="margin:5px 0;"><b>층/총층:</b> {flr}</p>
            <p style="margin:5px 0;"><b>면적:</b> 공급 {s1}㎡ / 전용 {s2}㎡</p>
            <p style="margin:5px 0;"><b>특징:</b> {ftr}</p>
            <p style="margin-top:10px;"><a href="https://m.land.naver.com/article/info/{ano}" target="_blank" style="display:inline-block; padding:8px 15px; background-color:#03cf5d; color:white; text-decoration:none; border-radius:4px; font-weight:bold;">네이버 부동산 매물 바로가기</a></p>
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
        
        time.sleep(1) # 요청 간격 차단 방지용 딜레이

    if new_listings:
        print(f"새로운 매물 {len(new_listings)}건을 발견했습니다!")
        send_email(new_listings)
    else:
        print("새로운 매물이 없습니다.")

    save_seen(seen)

if __name__ == "__main__":
    main()
