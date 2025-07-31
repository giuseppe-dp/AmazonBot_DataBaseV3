try:
  from setuptools import setup
except ImportError:
  from distutils.core import setup

config = {
  'description': 'AmazonBot with database',
  'author': 'TheCringeHat',
  'url': 'URL to get it at.',
  'download_url': 'Where to download it.',
  'author_email': 'calcio.79@libero.it',
  'version': '1.4',
  'install_requires': ['python-telegram-bot==22.1','paapi5-python-sdk','requests', 'python-dotenv', 'nest_asyncio'],
  'packages': ['packages'],
  'scripts': [],
  'name': 'AmazonBot_DataBase'
}

setup(**config)