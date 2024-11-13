from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.services.databases import Databases

client = Client()
client.set_endpoint('https://cloud.appwrite.io/v1')
client.set_project('6602a79975c04c55b0a3')
client.set_key('9afde2575f681408d5e462e36f2db8cd49a499f165633e6c2171d12e7abc7a734bffd964b19cc581856e574d52518dfeddc7e088a847c119405beac7af88d1d8473b54482a31598bc8069ba6cef870825fb7bffe28df346b3080349d273a90c5482c393759a8885fe7318353e91805c2ddc825f8bfd02a7dc8229074d91740b9')
def get_storage():
    return Storage(client)
def get_database():
    return Databases(client)