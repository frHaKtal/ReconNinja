import base64
import sqlite3
import requests
import socket
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import tldextract

# Connexion à la base de données
#conn = sqlite3.connect('database.db')
#cursor = conn.cursor()

def get_db_connection():
    return sqlite3.connect('database.db')


def get_spfdmarc(domain):

    #print(f"✔️  \033[1m{len(domains)}\033[0m domain find")
    #spf = curl -s https://dmarcly.com/server/spf_check.php?domain={domain} | grep -q --color=auto "SPF record not found" && echo -e "[!]\e[31m SPF RECORD NOT FOUND\e[0m" || echo -e "[●]\e[33m SPF RECORD VALID\e[0m"
    #dmarc = curl -s https://dmarcly.com/server/dmarc_check.php\?domain\={domain} | grep -q --color=auto "DMARC record not found" && echo -e "[!]\e[31m DMARC RECORD NOT FOUND\e[0m" || echo -e "[●]\e[33m DMARC RECORD VALID\e[0m"
    url_spf = f"https://dmarcly.com/server/spf_check.php?domain={domain}"
    response_spf = requests.get(url_spf)
    if "SPF record not found" in response_spf.text:
        #print("\033[31m[!]\033[0m SPF RECORD NOT FOUND")
        spf_result = "❌"
    else:
        #print("\033[33m[●]\033[0m SPF RECORD VALID")
        spf_result = "✔️ "

    url_dmarc = f"https://dmarcly.com/server/dmarc_check.php?domain={domain}"
    response_dmarc = requests.get(url_dmarc)
    if "DMARC record not found" in response_dmarc.text:
        #print("\033[31m[!]\033[0m DMARC RECORD NOT FOUND")
        dmarc_result = "❌"
    else:
        #print("\033[33m[●]\033[0m DMARC RECORD VALID")
        dmarc_result = "✔️ "

    return spf_result + dmarc_result

def get_ip(domain):

    try:
        ip_address = socket.gethostbyname(domain)
        return ip_address
    except socket.error as e:
        pass
        #print(f"❌ Error resolving {domain_name}: {e}")
    return None

def get_http_status(domain):

    url = f"http://{domain}"
    try:
        response = requests.get(url, timeout=5)  # Ajoute un timeout pour éviter de bloquer
        return response.status_code
    except requests.RequestException as e:
        #print(f"❌ Error fetching {url}: {e}")
        return None

def get_techno(domain):
    result = subprocess.run(f"echo {domain} | httpx --tech-detect --silent | grep -oP '\\[.*?\\]'",
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    return result.stdout


def get_title(domain):
    url = f"http://{domain}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.title.string if soup.title else 'No title found'
        else:
            return 'No title found'
    except requests.RequestException as e:
        pass
        #print(f"❌ Error fetching {url}: {e}")
        return 'No title found'


def scan_naabu_fingerprint(domain):
    try:
        # Exécuter la commande avec un timeout de 10 secondes
        result = subprocess.run(
            f"naabu -host {domain} -ec -cdn -silent 2>/dev/null | fingerprintx",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10  # Timeout de 10 secondes
        )

        # Renvoyer la sortie de la commande (stdout)
        return result.stdout
    except subprocess.TimeoutExpired:
        #print(f"⏰ Scan {dom} Timeout")
        return "Timeout"
    except Exception as e:
        pass
        #print(f"❌ Error run {dom}: {e}")
        return None

def take_screenshot(domain_name):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Ouvrir la page du domaine
        driver.get(f"http://{domain_name}")
        screenshot = driver.get_screenshot_as_png()

        # Encoder en base64
        screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')
        return screenshot_base64

    except Exception as e:
        #print(f"Failed to take screenshot for {domain_name}: {e}")
        return None
    finally:
        driver.quit()

def add_dom(program_name, domain):
    # Ouvrir une nouvelle connexion et un curseur pour ce thread
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    #conn = get_db_connection()
    #cursor = conn.cursor()

    try:


        cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (domain,))
        existing_domain = cursor.fetchone()

        if existing_domain:
            print(f"⚠️  Domain '{domain}' already exists.")
            return

        #print(f"Adding domain: {domain} to program: {program_name}")

        # Récupérer les informations d'énumération
        ip = get_ip(domain)
        open_ports = scan_naabu_fingerprint(domain)
        #spfdmarc = get_spfdmarc(domain)
        extracted = tldextract.extract(domain)

        # Récupérer uniquement le spfdmarc si le domaine principal n'est pas déjà présent
        domain_main = f"{extracted.domain}.{extracted.suffix}"
        #cursor.execute('SELECT spfdmarc FROM domain_details JOIN domains ON domains.id = domain_details.domain_id WHERE domain_name LIKE ?', (f"%.{domain_main}",))
        #existing_main_domain = cursor.fetchone()

        #if existing_main_domain:
        #    spfdmarc = existing_main_domain[0]
        #else:
        #    spfdmarc = get_spfdmarc(domain_main)  # Récupérer spfdmarc seulement si le domaine principal n'est pas présent

        spfdmarc = get_spfdmarc(domain_main)
        if not ip or not open_ports:
            http_status = None
            techno = None
            open_ports = None
            screenshot = None
            title = None
        else:
            http_status = get_http_status(domain)
            techno = get_techno(domain)
            open_ports = scan_naabu_fingerprint(domain)
            screenshot = take_screenshot(domain)
            title = get_title(domain)


        # Récupérer l'ID du programme
        cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
        program_id = cursor.fetchone()

        if program_id:
            # Ajouter le domaine dans la table domains
            cursor.execute('''
                INSERT INTO domains (program_id, domain_name) VALUES (?, ?)
            ''', (program_id[0], domain))
            domain_id = cursor.lastrowid

            # Ajouter les détails du domaine dans la table domain_details
            cursor.execute('''
                INSERT INTO domain_details (domain_id, title, ip, http_status, techno, open_port, screen, spfdmarc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (domain_id, title, ip, http_status, techno, open_ports, screenshot, spfdmarc))

            conn.commit()
            #print(f"✔️ Domain {domain} added successfully.")
        else:
            print(f"❌ Program {program_name} not found.")

    except Exception as e:
        print(f"❌ Failed to add domain {domain}: {e}")
    finally:
        cursor.close()
        conn.close()
