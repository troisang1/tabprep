"""Bot-IoT dataset package — UNSW Canberra IoT botnet flows (Koroniotis et al., 2018).

Importing this package registers `BotIoTLoader` (`@loader("bot_iot")`)
and `BotIoTDownloader` (`@downloader("bot_iot")`).
"""
from tabprep.datasets.bot_iot.downloader import BotIoTDownloader  # noqa: F401
from tabprep.datasets.bot_iot.loader import BotIoTLoader  # noqa: F401
