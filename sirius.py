import asyncio
from base64 import b64encode
from datetime import datetime, timedelta
from os.path import exists

import aiohttp
from rich import print


async def main() -> None:
    if not exists("token"):
        with open("token", "w") as file:
            file.write(
                b64encode(
                    f"{input('login -> ')}:{input('password -> ')}".encode("UTF-8")
                ).decode("UTF-8")
            )

    with open("token") as file:
        token = file.read()

    async with aiohttp.ClientSession(
        headers={
            "authorization": f"Basic {token}",
        },
    ) as session:
        async with session.get(
            "https://online.sochisirius.ru/schedule?task=getTimeline&mobile=1&onRec=1&app=100220230510118067"
        ) as response:
            data = await response.json()

        user = data["user"]

        events = {}
        num = 1
        for event in [event for events in data["events"].values() for event in events]:
            id = int(event["ids"])
            name = str(event["enm"])
            start = datetime.strptime(
                f'{event["db"]} {event["tb"]}', "%d.%m.%Y %H:%M:%S"
            )
            register_from = start - timedelta(hours=int(event["regStartDate"]))
            register_to = start - timedelta(hours=int(event["regEndDate"]))

            limit = int(event["peopleLimit"])
            enrolled = int(event["enrolledAll"])
            is_enrolled = bool(event.get("enrolled", 0))

            if (
                limit == enrolled
                or is_enrolled
                or register_to < datetime.now()
                or register_from > (datetime.now() + timedelta(2))
            ):
                continue

            print(f"{num: >3}", end=" - ")
            if register_from > datetime.now():
                print(
                    f"{name}\n     ",
                    start,
                    f"({register_from})",
                    f"({int((register_from - datetime.now()).total_seconds())})",
                )
            else:
                print(f"{name}\n     ", start)
            print("------")

            events[num] = (id, register_from)
            num += 1

        id, register_from = events[int(input("ID -> "))]

        if register_from > datetime.now():
            delta = int((register_from - datetime.now()).total_seconds()) - 2
            for num in range(delta):
                print(f"{delta - num}", end="\r")
                await asyncio.sleep(1)

        num = 1
        while True:
            async with session.post(
                "https://online.sochisirius.ru/forms?fid=199910202940",
                data={
                    "id": id,
                    "fid": 199910202940,
                    "act": "send",
                    "__api": 2,
                    "f_1032910003": int(user["id"]),
                    "task": "edit",
                },
            ) as response:
                data = await response.json()
                if "e" not in data["enrolled"]:
                    print(f"OK, attempt {num}")
                    break
                print(f"ERROR, attempt {num}")
            num += 1


asyncio.run(main())
