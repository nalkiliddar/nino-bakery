from flask import Flask, render_template, request, jsonify
from azure.storage.blob import BlobServiceClient
from azure.communication.callautomation import CallAutomationClient
import uuid
import json
from datetime import datetime
import config

app = Flask(__name__)

# Azure Blob
blob_service_client = BlobServiceClient.from_connection_string(
    config.AZURE_STORAGE_CONNECTION_STRING
)

container_client = blob_service_client.get_container_client(
    config.CONTAINER_NAME
)

# Azure Communication Services
call_client = CallAutomationClient.from_connection_string(
    config.ACS_CONNECTION_STRING
)


@app.route("/")
def home():
    return render_template(
        "index.html",
        phone=config.ACS_PHONE_NUMBER
    )


# Order API
@app.route("/place_order", methods=["POST"])
def place_order():

    data = request.json

    order = {
        "id": str(uuid.uuid4()),
        "name": data["name"],
        "email": data["email"],
        "phone": data["phone"],
        "item": data["item"],
        "date": data["date"],
        "timestamp": str(datetime.utcnow())
    }

    blob_name = f"order_{order['id']}.json"

    container_client.upload_blob(
        blob_name,
        json.dumps(order),
        overwrite=True
    )

    return jsonify({"message": "Order successfully placed!"})


# Webhook for incoming calls
@app.route("/incomingCall", methods=["POST"])
def incoming_call():

    events = request.json

    for event in events:

        if event["type"] == "Microsoft.Communication.IncomingCall":

            incoming_context = event["data"]["incomingCallContext"]

            callback_url = "https://YOURDOMAIN/api/callback"

            call_client.answer_call(
                incoming_call_context=incoming_context,
                callback_url=callback_url
            )

    return "OK"


# After call is answered route to agent
@app.route("/api/callback", methods=["POST"])
def callback():

    events = request.json

    for event in events:

        if event["type"] == "Microsoft.Communication.CallConnected":

            call_connection_id = event["data"]["callConnectionId"]

            call_connection = call_client.get_call_connection(
                call_connection_id
            )

            call_connection.add_participant({
                "phoneNumber": config.SUPPORT_AGENT_PHONE
            })

    return "OK"


if __name__ == "__main__":
    app.run(debug=True)