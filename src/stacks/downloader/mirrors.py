import argparse
import re
import sys
import time
import logging
import random
import requests
import subprocess
import shutil
import tempfile
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup
from stacks.constants import CACHE_PATH

# Cookie cache path
COOKIE_CACHE_PATH = Path(CACHE_PATH) / "cookie.json"