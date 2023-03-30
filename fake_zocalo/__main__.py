import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Tuple

import ispyb.sqlalchemy
import pika
import yaml
from ispyb.sqlalchemy import DataCollection
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import BasicProperties
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from artemis.external_interaction.system_tests.conftest import (
    TEST_RESULT_LARGE,
    TEST_RESULT_SMALL,
)

NO_DIFFRACTION_PREFIX = "NO_DIFF"

MULTIPLE_CRYSTAL_PREFIX = "MULTI_X"

DEV_ISPYB_CONFIG = "/dls_sw/dasc/mariadb/credentials/ispyb-dev.cfg"


def load_configuration_file(filename):
    conf = yaml.safe_load(Path(filename).read_text())
    return conf


def get_dcgid_and_prefix(dcid: int, Session) -> Tuple[int, str]:
    try:
        with Session() as session:
            query = (
                session.query(DataCollection)
                .filter(DataCollection.dataCollectionId == dcid)
                .first()
            )
            dcgid: int = query.dataCollectionGroupId
            prefix: str = query.imagePrefix
    except Exception as e:
        print("Exception occured when reading from ISPyB database:\n")
        print(e)
        dcgid = 4
        prefix = ""
    return dcgid, prefix


def make_result(payload):
    res = {
        "environment": {"ID": "6261b482-bef2-49f5-8699-eb274cd3b92e"},
        "payload": payload,
        "recipe": {
            "start": [[1, payload]],
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
    return res


def main():
    url = ispyb.sqlalchemy.url(DEV_ISPYB_CONFIG)
    engine = create_engine(url, connect_args={"use_pure": True})
    Session = sessionmaker(engine)

    config = load_configuration_file(
        os.path.expanduser("~/.zocalo/rabbitmq-credentials.yml")
    )
    creds = pika.PlainCredentials(config["username"], config["password"])
    params = pika.ConnectionParameters(
        config["host"], config["port"], config["vhost"], creds
    )

    results = defaultdict(lambda: make_result(TEST_RESULT_LARGE))
    results[NO_DIFFRACTION_PREFIX] = make_result([])
    results[MULTIPLE_CRYSTAL_PREFIX] = make_result(
        [*TEST_RESULT_LARGE, *TEST_RESULT_SMALL]
    )

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

            dcid = message.get("parameters").get("ispyb_dcid")
            print(f"Getting info for dcid {dcid} from ispyb:")
            dcgid, prefix = get_dcgid_and_prefix(dcid, Session)
            print(f"Dcgid {dcgid} and prefix {prefix}")

            time.sleep(1)
            print('Sending "results"...')
            resultprops = BasicProperties(
                delivery_mode=2,
                headers={"workflows-recipe": True, "x-delivery-count": 1},
            )

            result = results[prefix]
            result["recipe"]["1"]["parameters"]["dcid"] = str(dcid)
            result["recipe"]["1"]["parameters"]["dcgid"] = str(dcgid)

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
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Shutting down gracefully")
        channel.close()


if __name__ == "__main__":
    main()
