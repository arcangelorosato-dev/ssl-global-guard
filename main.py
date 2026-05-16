import sys
import datetime
import socket
import ssl
from flask import Flask, request, jsonify
import urllib.request

app = Flask(__name__)

def ottieni_giorni_ssl(hostname):
    """connessione ssl nativa per estrarre i giorni esatti senza errori"""
    # pulizia dell'url per estrarre solo il dominio pulito
    hostname = hostname.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    
    contesto = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, 443), timeout=5) as calza:
            with contesto.wrap_socket(calza, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                scadenza_str = cert['notAfter']
                # formato: 'May 16 12:47:24 2026 GMT'
                data_scadenza = datetime.datetime.strptime(scadenza_str, '%b %d %H:%M:%S %Y %Z')
                oggi = datetime.datetime.utcnow()
                return (data_scadenza - oggi).days, data_scadenza.strftime('%d/%m/%Y')
    except Exception as e:
        return None, str(e)


def esegui_controllo_ssl(url_da_controllare):
    # pulizia url
    url_completo = url_da_controllare if url_da_controllare.startswith(("http://", "https://")) else "https://" + url_da_controllare
    hostname_pulito = url_completo.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    
    # 1. controllo dello stato http reale
    contesto_aperto = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(
            url_completo, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, context=contesto_aperto, timeout=5) as risposta:
            status_sito = risposta.getcode()
    except urllib.error.HTTPError as e:
        # se c'è un errore http (500, 503, 404, ecc.) interrompiamo subito e mandiamo l'allarme!
        return {
            "status": "failed",
            "url": url_da_controllare,
            "ssl_valido": False,
            "giorni_rimanenti": -1,
            "data_scadenza": "N/D",
            "messaggio": f"🚨 CRITICO: il sito risponde con codice di errore http {e.code}!"
        }, 200
    except Exception as errore_connessione:
        return {
            "status": "failed",
            "url": url_da_controllare,
            "ssl_valido": False,
            "giorni_rimanenti": -1,
            "data_scadenza": "N/D",
            "messaggio": "❌ il sito è offline o l'url è inesistente"
        }, 200

    # 2. se lo stato http è 200, allora controlliamo i giorni dell'ssl
    giorni, data_scad_str = ottieni_giorni_ssl(hostname_pulito)

    if giorni is None:
        return {
            "status": "failed",
            "url": url_da_controllare,
            "ssl_valido": False,
            "giorni_rimanenti": -1,
            "data_scadenza": "N/D",
            "messaggio": f"❌ certificato ssl non valido o scaduto: {data_scad_str}"
        }, 200

    return {
        "status": "success",
        "url": url_da_controllare,
        "ssl_valido": True,
        "giorni_rimanenti": giorni,
        "data_scadenza": data_scad_str,
        "messaggio": "certificato ssl valido e verificato"
    }, 200

@app.route("/check-ssl", methods=["POST"])
def check_ssl_endpoint():
    dati = request.get_json()
    if not dati or "url" not in dati:
        return jsonify({"status": "error", "message": "url mancante nel body"}), 400
    
    risultato, status_code = esegui_controllo_ssl(dati["url"])
    return jsonify(risultato), status_code

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url_cli = sys.argv[1]
        print(f"avvio controllo cli per: {url_cli}\n---")
        risultato, _ = esegui_controllo_ssl(url_cli)
        for chiave, valore in risultato.items():
            print(f"{chiave}: {valore}")
    else:
        print("avvio del server per n8n su http://localhost:5000...")
        app.run(host="0.0.0.0", port=5000, debug=True)