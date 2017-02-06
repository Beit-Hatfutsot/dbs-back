from lxml import etree
from flask import current_app
from zeep import Client


def get_clearmash_client(ep):
    ''' return a client, including the required soap headers
        :param ep: the name of the service to use
    '''

    client = Client("{}/API/V5/Services/{}.svc?wsdl"
                    .format(current_app.conf.clearmash_url,
                            ep)
                   )
    header = etree.Element('ClientToken')
    header.text = current_app.conf.clearmash_token
    client.set_default_soapheaders([header])
    return client
