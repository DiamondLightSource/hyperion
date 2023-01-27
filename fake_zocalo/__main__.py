import json
import os
import time
from pathlib import Path

import pika
import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import BasicProperties

NO_DIFFRACTION_ID = 1


def load_configuration_file(filename):
    conf = yaml.safe_load(Path(filename).read_text())
    return conf


def main():
    config = load_configuration_file(
        os.path.expanduser("~/.zocalo/rabbitmq-credentials.yml")
    )
    creds = pika.PlainCredentials(config["username"], config["password"])
    params = pika.ConnectionParameters(
        config["host"], config["port"], config["vhost"], creds
    )

    single_crystal_result = {
        "environment": {"ID": "6261b482-bef2-49f5-8699-eb274cd3b92e"},
        "payload": [{"max_voxel": [1, 2, 3], "centre_of_mass": [1.2, 2.3, 3.4]}],
        "recipe": {
            "start": [
                [1, [{"max_voxel": [1, 2, 3], "centre_of_mass": [1.2, 2.3, 3.4]}]]
            ],
            "1": {
                "service": "Send XRC results to GDA",
                "queue": "xrc.i03",
                "exchange": "results",
                "parameters": {"dcid": "2", "dcgid": "4"},
            },
        },
        "recipe-path": [],
        "recipe-pointer": 1,
    }

    no_diffraction_result = {
        "environment": {"ID": "6261b482-bef2-49f5-8699-eb274cd3b92e"},
        "payload": [],
        "recipe": {
            "start": [
                [1, [{"max_voxel": [1, 2, 3], "centre_of_mass": [1.2, 2.3, 3.4]}]]
            ],
            "1": {
                "service": "Send XRC results to GDA",
                "queue": "xrc.i03",
                "exchange": "results",
                "parameters": {
                    "dcid": str(NO_DIFFRACTION_ID),
                    "dcgid": str(NO_DIFFRACTION_ID),
                },
            },
        },
        "recipe-path": [],
        "recipe-pointer": 1,
    }

    def on_request(ch: BlockingChannel, method, props, body):
        print(
            f"recieved message: \n properties: \n\n {method} \n\n {props} \n\n{body}\n"
        )
        try:
            message = json.loads(body)
        except Exception:
            print("Malformed message body.")
            return
        if message.get("parameters").get("event") == "end":
            print('Doing "processing"...')
            time.sleep(3)
            print('Sending "results"...')
            resultprops = BasicProperties(
                delivery_mode=2,
                headers={"workflows-recipe": True, "x-delivery-count": 1},
            )

            if message.get("parameters").get("ispyb_dcid") == NO_DIFFRACTION_ID:
                result = no_diffraction_result
            else:
                result = single_crystal_result

            print(f"Sending results {result}")
            result_chan = conn.channel()
            result_chan.basic_publish(
                "results", "xrc.i03", json.dumps(result), resultprops
            )
            print("Finished.\n")
        ch.basic_ack(method.delivery_tag, False)

    conn = pika.BlockingConnection(params)
    channel = conn.channel()
    channel.basic_consume(queue="processing_recipe", on_message_callback=on_request)
    print("Listening for zocalo requests")
    channel.start_consuming()


if __name__ == "__main__":
    main()
