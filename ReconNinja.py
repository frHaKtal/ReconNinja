import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import print_formatted_text
import sqlite3
from tabulate import tabulate
import requests
import socket
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
#from webdriver_manager.chrome import ChromeDriverManager
import os
from PIL import Image
import shutil
import subprocess
from bs4 import BeautifulSoup

#driver = webdriver.Chrome(ChromeDriverManager().install())
# Code couleur ANSI pour la ligne grise
GREY_BACKGROUND = '\033[48;5;240m'
RESET_COLOR = '\033[0m'

# Connexion à la base de données (création du fichier si inexistant)
conn = sqlite3.connect('database.db')

# Création d'un curseur pour exécuter des requêtes SQL
cursor = conn.cursor()

# Création des tables

##Table programs
cursor.execute('''
    CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_name TEXT NOT NULL,
    com TEXT
)
''')

##Table domains
cursor.execute('''
    CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain_name TEXT,
        program_id INTEGER,
        FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
    )
''')

##Table domain_details
cursor.execute('''
    CREATE TABLE IF NOT EXISTS domain_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    http_status TEXT,
    ip TEXT,
    title TEXT,
    techno TEXT,
    open_port TEXT,
    screen BLOB,
    fuzz TEXT,
    nuclei TEXT,
    domain_id INTEGER,
    com TEXT,
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
    )
''')


# Dictionnaire contenant les commandes et leurs descriptions
commands_with_descriptions = {
    'exit': 'Exit the program',
    'add': 'Add domain: add domain.com (without http) or add domain1.com domain2.com',
    'add_com': 'Add comment to domain or program (add_com domain domain.com "the best domain")',
    'rm': 'Remove a domain (without http) or program (rm domain/program xxx',
    'list': 'Domain of program list (list domain/program)',
    'clear': 'Clear screen',
    'scan': 'Perform a signature scan on all discovered servers',
}

class CommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        # Renvoyer les suggestions et descriptions des commandes
        word_before_cursor = document.get_word_before_cursor()
        for command, description in commands_with_descriptions.items():
            if command.startswith(word_before_cursor):
                yield Completion(command, start_position=-len(word_before_cursor), display_meta=description)

def add_com(target_type, target_name, comment):
    """
    Ajoute ou met à jour un commentaire pour un programme ou un domaine.
    :param target_type: Le type de cible ('program' ou 'domain')
    :param target_name: Le nom du programme ou du domaine
    :param comment: Le commentaire à ajouter ou mettre à jour
    """
    if target_type == 'program':
        # Vérifier si le programme existe
        cursor.execute('SELECT id FROM programs WHERE program_name = ?', (target_name,))
        program = cursor.fetchone()

        if program:
            program_id = program[0]
            # Ajouter ou mettre à jour le commentaire du programme
            cursor.execute('UPDATE programs SET com = ? WHERE id = ?', (comment, program_id))
            conn.commit()
            print(f"✔️ Comment added to program '{target_name}'")
        else:
            print(f"❌ Program '{target_name}' not found.")
    elif target_type == 'domain':
        # Vérifier si le domaine existe
        cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (target_name,))
        domain = cursor.fetchone()

        if domain:
            domain_id = domain[0]
            # Ajouter ou mettre à jour le commentaire du domaine
            cursor.execute('UPDATE domain_details SET com = ? WHERE domain_id = ?', (comment, domain_id))
            conn.commit()
            print(f"✔️ Comment added to domain '{target_name}'")
        else:
            print(f"❌ Domain '{target_name}' not found.")
    else:
        print(f"❌ Invalid target type. Use 'program' or 'domain'.")


def get_title(domain_name):
    url = f"http://{domain_name}"
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

def enum_domain(dom):
    print(f"✔️  Enumeration for domain: \033[1m{dom}\033[0m")
    result = subprocess.run(f"subfinder -d {dom} -silent",
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    return result.stdout


def take_screenshot(program_id, domain_name):
    # Configurer Chrome en mode headless (sans interface graphique)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")
    # Créer l'instance de Chrome headless
    #driver = webdriver.Chrome(executable_path='/usr/local/bin')
    driver = webdriver.Chrome(options=chrome_options)
    try:
        # Ouvrir la page du domaine
        driver.get(f"http://{domain_name}")

        # Prendre le screenshot en PNG
        screenshot = driver.get_screenshot_as_png()

        # Encoder le screenshot en base64 pour stocker dans la base de données
        screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')

        # Vérifier si l'enregistrement existe déjà
        cursor.execute('''
            SELECT id FROM domain_details WHERE domain_id = (SELECT id FROM domains WHERE domain_name = ?)
        ''', (domain_name,))
        existing_record = cursor.fetchone()

        if existing_record:
            # Si l'enregistrement existe, le mettre à jour
            cursor.execute('''
                UPDATE domain_details SET screen = ? WHERE id = ?
            ''', (screenshot_base64, existing_record[0]))
        else:
            # Sinon, insérer un nouvel enregistrement
            cursor.execute('''
                INSERT INTO domain_details (domain_id, screen) VALUES (
                    (SELECT id FROM domains WHERE domain_name = ?), ?
                )
            ''', (domain_name, screenshot_base64))

        conn.commit()

        #print(f"✔️ Screenshot taken and stored for \033[1m{domain_name}\033[0m")

    except Exception as e:
         pass
        #print(f"❌ Failed to take screenshot for \033[1m{domain_name}\033[0m: {e}")

    finally:
        driver.quit()


def display_screenshot_with_imgcat(screenshot_data):
    # Convertir les données blob en image utilisable
    #print(screenshot_data)
    image_data = base64.b64decode(screenshot_data)

    # Sauvegarder temporairement l'image pour imgcat
    temp_image_path = "/tmp/temp_screenshot.png"
    with open(temp_image_path, "wb") as img_file:
        img_file.write(image_data)

    # Utiliser imgcat pour afficher l'image dans le terminal
    os.system(f"imgcat {temp_image_path}")

    # Supprimer le fichier temporaire après affichage
    os.remove(temp_image_path)

def scan_naabu_fingerprint(dom):
    try:
        # Exécuter la commande avec un timeout de 10 secondes
        result = subprocess.run(
            f"naabu {dom} -silent 2>/dev/null | fingerprintx",
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


def get_techno(dom):

    result = subprocess.run(f"echo {dom} | httpx --tech-detect --silent | grep -oP '\\[.*?\\]'",
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    return result.stdout

def add_dom(program_name, dom):
    # Récupérer l'ID du programme en fonction du nom du programme
    cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
    program = cursor.fetchone()
    program_id = program[0]

    # Vérifier si le domaine existe déjà dans la base de données
    cursor.execute('SELECT id FROM domains WHERE domain_name = ? AND program_id = ?', (dom, program_id))
    domain = cursor.fetchone()
    if domain:
        print(f"❌ Domain \033[1m'{dom}'\033[0m already exists.")
        return

    # Récupérer l'ID du programme auquel vous souhaitez ajouter un domaine
    cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
    program_id = cursor.fetchone()

    if program_id:
        program_id = program_id[0]

        # Batch les requêtes avant de committer
        try:
            conn.execute('BEGIN')  # Démarre une transaction

            # Récupérer l'adresse IP du domaine
            ip_address = get_ip(dom)

            # Si pas d'IP trouvée, utiliser une valeur par défaut (ex: None ou '')
            if not ip_address:
                print(f"⚠️ No IP found for {dom}, proceeding without IP.")
                ip_address = None  # Ou '' si la colonne ne supporte pas NULL
                http_status = None
                title = None
                techno = None
                open_ports = None
            else:
                # Récupérer les autres informations si l'IP est présente ou non
                http_status = get_http_status(dom)
                title = get_title(dom)
                techno = get_techno(dom)
                open_ports = scan_naabu_fingerprint(dom)

            # Insérer le domaine dans la base de données même sans IP
            cursor.execute('INSERT INTO domains (domain_name, program_id) VALUES (?, ?)', (dom, program_id))
            domain_id = cursor.lastrowid

            # Insérer les détails du domaine
            cursor.execute('''
                INSERT INTO domain_details (http_status, ip, title, techno, open_port, domain_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (http_status, ip_address, title, techno, open_ports, domain_id))

            # Commit tous les changements d'un coup
            conn.commit()

            if ip_address:
                # Capture d'écran après l'insertion, si nécessaire
                take_screenshot(domain_id, dom)
            print(f"✔️ Domain \033[1m{dom}\033[0m added to \033[1m{sys.argv[1]}\033[0m program")
        except Exception as e:
            conn.rollback()  # Annule les changements si une erreur survient
            print(f"❌ Error to add domain '{dom}': {e}")
    else:
        print(f"❌ Program '{program_name}' not found.")



def get_http_status(domain_name):
    url = f"http://{domain_name}"
    try:
        response = requests.get(url, timeout=5)  # Ajoute un timeout pour éviter de bloquer
        return response.status_code
    except requests.RequestException as e:
        #print(f"❌ Error fetching {url}: {e}")
        return None

def get_ip(domain_name):
    try:
        ip_address = socket.gethostbyname(domain_name)
        return ip_address
    except socket.error as e:
        pass
        #print(f"❌ Error resolving {domain_name}: {e}")
        return None


def add_program(program_name):
    # Vérifier si le programme existe déjà
    cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
    if cursor.fetchone() is not None:
        print(f"❌ Program \033[1m'{program_name}'\033[0m already exists.")
        return

    # Si le programme n'existe pas, l'ajouter
    cursor.execute('''
        INSERT INTO programs (program_name)
        VALUES (?)
    ''', (program_name,))
    conn.commit()
    print(f"✔️ Program \033[1m'{program_name}'\033[0m has been added.")

def rm(entity_name, entity_type):
    cursor = conn.cursor()

    if entity_type == 'program':
        # Vérifier si le programme existe
        cursor.execute('SELECT id FROM programs WHERE program_name = ?', (entity_name,))
        program = cursor.fetchone()
        if program:
            # Supprimer le programme
            cursor.execute('DELETE FROM programs WHERE id = ?', (program[0],))
            conn.commit()
            print(f"✔️ Program \033[1m'{entity_name}'\033[0m has been deleted.")
        else:
            print(f"❌ Program \033[1m'{entity_name}'\033[0m not found.")

    elif entity_type == 'domain':
        # Vérifier si le domaine existe
        cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (entity_name,))
        domain = cursor.fetchone()

        if domain:
            # Supprimer le domaine
            cursor.execute('DELETE FROM domains WHERE id = ?', (domain[0],))
            conn.commit()
            print(f"✔️ Domain \033[1m'{entity_name}'\033[0m has been deleted.")
        else:
            print(f"❌ Domain \033[1m'{entity_name}'\033[0m not found.")

    else:
        print("❌ Invalid entity type. Use 'program' or 'domain'.")


def list_programs(conn):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, program_name, com FROM programs
    ''')
    programs = cursor.fetchall()

    for program in programs:
        print(f"Program: \033[1m{program[1]}\033[0m - Comment: \033[1m{program[2]}\033[0m")

def list_all_domains():
    cursor.execute('SELECT domain_name, program_id FROM domains')
    domains = cursor.fetchall()
    print("Current domains in the database:")
    for domain in domains:
        print(f"Domain: {domain[0]}, Program ID: {domain[1]}")


def list(entity_type, program_name=None):
    cursor = conn.cursor()

    if entity_type == 'program':
        cursor.execute('''
            SELECT id, program_name, com FROM programs
        ''')
        programs = cursor.fetchall()

        if programs:
            print("📄 List of programs:")
            for program in programs:
                print(f"Program: \033[1m{program[1]}\033[0m - Comment: \033[1m{program[2]}\033[0m")
        else:
            print("❌ No programs found.")
    elif entity_type == 'domain':
        if program_name:
            # Récupérer l'ID du programme
            cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
            program = cursor.fetchone()

            if program:
                program_id = program[0]
                cursor.execute('''
                    SELECT domains.domain_name, domain_details.http_status, domain_details.ip, domain_details.title,
                           domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.com
                    FROM domains
                    INNER JOIN domain_details ON domains.id = domain_details.domain_id
                    WHERE domains.program_id = ?
                ''', (program_id,))
                domains = cursor.fetchall()

                if domains:
                    print(f"📄 List of domains for program \033[1m{program_name}\033[0m:")
                    for domain in domains:
                        domain_name, http_status, ip, title, techno, open_port, screen, comment = domain
                        print(f"\033[48;5;240m🌐 http://\033[1m{domain_name}\033[0m\n"
                              f"\033[48;5;240mHttp status: \033[1m{http_status}\033[0m\n"
                              f"\033[48;5;240mIP: \033[1m{ip}\033[0m\n"
                              f"\033[48;5;240mTitle: \033[1m{title}\033[0m\n"
                              f"\033[48;5;240mTech: \033[1m{techno}\033[0m\n"
                              f"\033[48;5;240mOpen port: \033[1m{open_port}\033[0m\n")

                        # Afficher le commentaire s'il existe
                        if comment:
                            print(f"\033[48;5;240mComment: \033[1m{comment}\033[0m\n")

                        # Afficher le screenshot s'il est disponible
                        if screen:
                            display_screenshot_with_imgcat(screen)
                            print("\n")
                        else:
                            print("No screenshot available.")
                            print("\n")
                else:
                    print(f"❌ No domains found for program \033[1m{program_name}\033[0m.")
            else:
                print(f"❌ Program \033[1m{program_name}\033[0m not found.")
        else:
            cursor.execute('''
                SELECT domains.domain_name, domain_details.http_status, domain_details.ip, domain_details.title,
                       domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.com
                FROM domains
                INNER JOIN domain_details ON domains.id = domain_details.domain_id
            ''')
            domains = cursor.fetchall()

            if domains:
                print("📄 List of domains:")
                for domain in domains:
                    domain_name, http_status, ip, title, techno, open_port, screen, comment = domain
                    print(f"\033[48;5;240m🌐 http://\033[1m{domain_name}\033[0m\n"
                          f"\033[48;5;240mHttp status: \033[1m{http_status}\033[0m\n"
                          f"\033[48;5;240mIP: \033[1m{ip}\033[0m\n"
                          f"\033[48;5;240mTitle: \033[1m{title}\033[0m\n"
                          f"\033[48;5;240mTech: \033[1m{techno}\033[0m\n"
                          f"\033[48;5;240mOpen port: \033[1m{open_port}\033[0m\n")

                    if comment:
                        print(f"\033[48;5;240mComment: \033[1m{comment}\033[0m\n")

                    if screen:
                        display_screenshot_with_imgcat(screen)
                        print("\n")
                    else:
                        print("No screenshot available.")
                        print("\n")
            else:
                print("❌ No domains found.")
    else:
        print("❌ Invalid entity type. Use 'program' or 'domain'.")


def list_dom(program_name):
    cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
    program = cursor.fetchone()

    if program:
        program_id = program[0]
        cursor.execute('''
            SELECT domains.domain_name, domain_details.http_status, domain_details.ip, domain_details.title, domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.com
            FROM domains
            INNER JOIN domain_details ON domains.id = domain_details.domain_id
            WHERE domains.program_id = ?
            ORDER BY
                CASE
                   WHEN domain_details.http_status = '200' THEN 1
                   WHEN domain_details.http_status IS NULL THEN 3
                   ELSE 2
                END
        ''', (program_id,))
        domains = cursor.fetchall()

        if domains:
            print(f"📄 List of domains for \033[1m'{program_name}'\033[0m:")

            for domain in domains:
                domain_name, http_status, ip, title, techno, open_port, screen, comment = domain

                # Afficher les informations du domaine
                print(f"\033[48;5;240m🌐 http://\033[1m{domain_name}\033[0m\n"
                      f"\033[48;5;240mHttp status: \033[1m{http_status}\033[0m\n"
                      f"\033[48;5;240mIP: \033[1m{ip}\033[0m\n"
                      f"\033[48;5;240mTitle: \033[1m{title}\033[0m\n"   # Ajout du titre
                      f"\033[48;5;240mTech: \033[1m{techno}\033[0m\n"
                      f"\033[48;5;240mOpen port: \033[1m{open_port}\033[0m\n")

                # Afficher le commentaire s'il existe
                if comment:
                    print(f"\033[48;5;240mComment: \033[1m{comment}\033[0m\n")

                # Afficher le screenshot si disponible
                if screen:
                    display_screenshot_with_imgcat(screen)
                    print("\n")
                else:
                    print("No screenshot available.")
                    print("\n")
        else:
            print(f"❌ No domains found for \033[1m'{program_name}'\033[0m.")
    else:
        print(f"❌ Program '{program_name}' not found.")



def main():
    # Créer une session pour la saisie interactive
    session = PromptSession()

    # Message d'instruction
    print_formatted_text("【welcome to ReconNinja v1.0 by _frHaKtal_】")
    print_formatted_text("‼️ Press tab for autocompletion and available commands\n")

    # Ajouter programme name de l'argument
    add_program(sys.argv[1])

    # Command completer avec descriptions
    command_completer = CommandCompleter()

    while True:
        try:
            # Attendre une commande avec autocomplétion et affichage des descriptions
            user_input = session.prompt(sys.argv[1] + ' ▶︎ ', completer=command_completer)

            # Séparer la commande et les arguments
            parts = user_input.split()
            if parts:
                command = parts[0]  # La commande principale
                args = parts[1:]    # Les arguments (s'il y en a)

                # Exécuter une commande en fonction de l'entrée utilisateur
                if command == 'exit':
                    print("Exiting...")
                    break
                elif command == 'list_program':
                    list_programs(conn)
                elif command == 'rm':
                    rm(args[1],args[0])
                elif command == 'add':
                    # Gérer plusieurs domaines dans args
                    for domain in args:
                        if '*.' in domain:
                            domain_enum = enum_domain(domain.lstrip('*.'))
                            domains = domain_enum.splitlines()
                            print(f"✔️  \033[1m{len(domains)}\033[0m domain find")
                            for subdomain in domains:
                                add_dom(sys.argv[1], subdomain)
                                #print(f"✔️ Domain \033[1m{subdomain}\033[0m added to \033[1m{sys.argv[1]}\033[0m program")
                        else:
                            add_dom(sys.argv[1], domain)
                            #print(f"✔️ Domain \033[1m{domain}\033[0m added to \033[1m{sys.argv[1]}\033[0m program")
                elif command == 'list':
                    if args:
                      list(args[0],sys.argv[1])
                elif command == 'clear':
                    os.system('clear')
                elif command == 'add_com':
                    if len(args) >= 3:
                        target_type = args[0]
                        target_name = args[1]
                        comment = " ".join(args[2:])  # Prendre le reste des arguments comme commentaire
                        add_com(target_type, target_name, comment)
                    else:
                        print("❌ Usage: add_com [program|domain] [name] [comment]")
                elif command == 'scan':
                    print("Performing a signature scan on all discovered servers...")
                else:
                    print(f"Unknown command: {user_input}")

        except (KeyboardInterrupt, EOFError):
            print("Exiting...")
            break

    conn.close()

if __name__ == "__main__":
    main()
