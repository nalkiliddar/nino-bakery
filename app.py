from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient
from azure.communication.callautomation import CallAutomationClient
import pyodbc
import json
import uuid
import config
from datetime import datetime

app = Flask(__name__)

# Azure clients
blob_service = BlobServiceClient.from_connection_string(
    config.BLOB_CONNECTION_STRING
)

call_client = CallAutomationClient.from_connection_string(
    config.ACS_CONNECTION_STRING
)


# SQL connection
def get_db_connection():

    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={config.SQL_SERVER};"
        f"DATABASE={config.SQL_DB};"
        f"UID={config.SQL_USER};"
        f"PWD={config.SQL_PASSWORD};"
        "Encrypt=yes;"
    )

    return conn


@app.route("/")
def index():
    return render_template("index.html", phone=config.ACS_PHONE_NUMBER)


# ---------------------------------------------------
# PLACE ORDER
# ---------------------------------------------------

@app.route("/place_order", methods=["POST"])
def place_order():

    data = request.json

    order = {
        "id": str(uuid.uuid4()),
        "customer": data["name"],
        "phone": data["phone"],
        "item": data["item"],
        "pickup_date": data["date"],
        "time": datetime.utcnow().isoformat()
    }

    container = blob_service.get_container_client(config.BLOB_CONTAINER)

    blob_name = f"order-{order['id']}.json"

    container.upload_blob(
        name=blob_name,
        data=json.dumps(order),
        overwrite=True
    )

    return jsonify({"message": "Order received!"})


# ---------------------------------------------------
# INCOMING CALL WEBHOOK
# ---------------------------------------------------

@app.route("/incoming_call", methods=["POST"])
def incoming_call():

    events = request.json

    for event in events:

        if event["eventType"] == "Microsoft.Communication.IncomingCall":

            incoming_context = event["data"]["incomingCallContext"]

            caller = event["data"]["from"]["phoneNumber"]["value"]
            called = event["data"]["to"]["phoneNumber"]["value"]

            log_call(caller, called)

            answer = call_client.answer_call(
                incoming_call_context=incoming_context,
                callback_url="https://yourdomain.com/callback"
            )

            connection_id = answer.call_connection_id

            connection = call_client.get_call_connection(connection_id)

            connection.transfer_call_to_participant({
                "phoneNumber": {
                    "value": config.SUPPORT_AGENT_PHONE
                }
            })

    return jsonify({"status": "ok"})


# ---------------------------------------------------
# LOG CALL
# ---------------------------------------------------

def log_call(caller, called):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO CallLogs (caller_number, called_number, call_time)
        VALUES (?, ?, ?)
        """,
        caller,
        called,
        datetime.utcnow()
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    app.run()