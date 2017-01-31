from flask import current_app
from zeep import Client, xsd


def get_clearmash_client(ep):
    ''' return a client, including the required soap headers
        :param ep: the name of the service to use
    '''

    client = Client("{}/API/V5/Services/{}.svc?wsdl"
                    .format(current_app.conf.clearmash_url,
                            ep)
                   )
    header = xsd.Element(
        '',
        xsd.ComplexType([
            xsd.Element(
                'ClientToken',
                xsd.String()),
        ])
    )
    client.set_default_soapheaders([
        header(ClientToken=current_app.conf.clearmash_token)
    ])
    return client
