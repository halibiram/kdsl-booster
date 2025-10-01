import http.client
import logging
import random
import string

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CpeEmulator:
    """
    A TR-069 Client Emulator to test the ACS Spoofer.
    This simulates a CPE connecting to an ACS, sending an Inform request,
    and handling the response.
    """
    def __init__(self, acs_host, acs_port=7547, timeout=10):
        self.acs_host = acs_host
        self.acs_port = acs_port
        self.timeout = timeout
        self.serial_number = "EMULATOR-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.software_version = "1.0.0-EMU"

    def _build_inform_request(self):
        """
        Constructs a realistic TR-069 Inform request SOAP message.
        """
        return f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap:Header>
</soap:Header>
<soap:Body>
<cwmp:Inform>
    <DeviceId>
        <Manufacturer>DSL Bypass Ultra</Manufacturer>
        <OUI>001122</OUI>
        <ProductClass>Keenetic-Emulator</ProductClass>
        <SerialNumber>{self.serial_number}</SerialNumber>
    </DeviceId>
    <Event soap:arrayType="cwmp:EventStruct[1]">
        <EventStruct>
            <EventCode>1 BOOT</EventCode>
            <CommandKey></CommandKey>
        </EventStruct>
    </Event>
    <MaxEnvelopes>1</MaxEnvelopes>
    <CurrentTime>{'2023-10-26T12:00:00Z'}</CurrentTime>
    <RetryCount>0</RetryCount>
    <ParameterList soap:arrayType="cwmp:ParameterValueStruct[1]">
        <ParameterValueStruct>
            <Name>InternetGatewayDevice.DeviceInfo.SoftwareVersion</Name>
            <Value xsi:type="xsd:string" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">{self.software_version}</Value>
        </ParameterValueStruct>
    </ParameterList>
</cwmp:Inform>
</soap:Body>
</soap:Envelope>"""

    def connect_and_inform(self):
        """
        Connects to the ACS and sends an Inform request.
        """
        logging.info(f"Emulator ({self.serial_number}) connecting to ACS at {self.acs_host}:{self.acs_port}")

        inform_payload = self._build_inform_request()

        try:
            conn = http.client.HTTPConnection(self.acs_host, self.acs_port, timeout=self.timeout)

            headers = {
                'Content-Type': 'text/xml; charset="utf-8"',
                'SOAPAction': '',
            }

            logging.info("Sending Inform request...")
            logging.debug(f"Request Body:\n{inform_payload}")

            conn.request("POST", "/", body=inform_payload.encode('utf-8'), headers=headers)

            response = conn.getresponse()
            response_data = response.read().decode('utf-8')

            logging.info(f"Received response from ACS: Status {response.status}")
            logging.info(f"Response Body:\n{response_data}")

            conn.close()
            return response_data

        except Exception as e:
            logging.error(f"Failed to connect or communicate with ACS: {e}")
            return None

if __name__ == '__main__':
    # Example usage:
    # This assumes the ACSSpoofer is running on localhost:7547
    print("CPE Emulator created. To run, instantiate the CpeEmulator class and call connect_and_inform().")
    print("Example: emulator = CpeEmulator('localhost'); emulator.connect_and_inform()")

    # To test against the spoofer from this project:
    # 1. Run the spoofer in one terminal: python src/tr069/acs_spoofer.py
    # 2. Run this emulator in another terminal: python src/tr069/client_emulator.py
    #
    # Example test run:
    # emulator = CpeEmulator('localhost')
    # emulator.connect_and_inform()