from flask import current_app
from zeep import Client, xsd


def get_clearmash_client():

    client = Client("{}/API/V5/Services/WebContentManagement.svc?wsdl"
                    .format(current_app.conf.clearmash_url))
    header = xsd.Element(
        '',
        xsd.ComplexType([
            xsd.Element(
                'ClientToken',
                xsd.String()),
        ])
    )
    header_value = header(ClientToken=current_app.conf.clearmash_token)
    return client, header_value
