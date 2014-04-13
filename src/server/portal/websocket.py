"""
Websockets Protocol

This implements WebSockets (http://en.wikipedia.org/wiki/WebSocket)
by use of the txws implementation (https://github.com/MostAwesomeDude/txWS).

Thanks to Ricard Pillosu whose Evennia plugin inspired this module.

Communication over the websocket interface is done with normal text
communication. A special case is OOB-style communication; to do this
the client must send data on the following form:
    OOB(oobfunc, args, kwargs)
    or
    OOB[(oobfunc, args, kwargs), ...]
where the tuple/list is sent json-encoded. The initial OOB-prefix
is used to identify this type of communication, all other data
is considered plain text (command input).

"""
import json
from twisted.internet.protocol import Protocol
from src.server.session import Session
from src.utils.logger import log_trace
from src.utils.utils import to_str
from src.utils.text2html import parse_html

class WebSocketProtocol(Protocol, Session):
    """
    This is called when the connection is first established
    """
    def connectionMade(self):
        """
        This is called when the connection is first established.
        """
        client_address = self.transport.client
        self.init_session("websocket", client_address, self.factory.sessionhandler)
        self.sessionhandler.connect(self)

    def disconnect(self, reason=None):
        """
        generic hook for the engine to call in order to
        disconnect this protocol.
        """
        if reason:
            self.data_out(text=reason)
        self.connectionLost(reason)

    def connectionLost(self, reason):
        """
        this is executed when the connection is lost for
        whatever reason. it can also be called directly, from
        the disconnect method
        """
        self.sessionhandler.disconnect(self)
        self.transport.loseconnection()

    def dataReceived(self, string):
        """
        Method called when data is coming in over
        the websocket connection.

        Type of data is identified by a 3-character
        prefix.
            OOB - This is an Out-of-band instruction. If so,
                  the remaining string should either be
                  a json packed tuple (oobfuncname, args, kwargs)
                  or a json-packed list of tuples
                  [(oobfuncname, args, kwargs), ...] to send to
                  the OOBhandler.
            any other prefix (or lack of prefix) is considered
                  plain text data, to be treated like a game
                  input command.
        """
        if string[:3] == "OOB":
            string = string[3:]
            try:
                oobdata = json.loads(string)
                if isinstance(oobdata, list):
                    for oobtuple in oobdata:
                        self.data_in(oob=oobtuple)
                elif isinstance(oobdata, tuple):
                    self.data_in(oob=oobtuple)
                else:
                    raise RuntimeError("OOB data is not list or tuple.")
            except:
                log_trace("Websocket malformed OOB request: %s" % oobdata)
        else:
            # plain text input
            self.data_in(text=string)

    def data_in(self, text=None, **kwargs):
        """
        Data Websocket -> Server
        """
        self.sessionhandler.data_in(self, text=text, **kwargs)

    def data_out(self, text=None, **kwargs):
        """
        Data Evennia -> Player.
        generic hook method for engine to call in order to send data
        through the websocket connection.

        valid webclient kwargs:
            oob=<string> - supply an Out-of-Band instruction.
            raw=True - no parsing at all (leave ansi-to-html markers unparsed)
            nomarkup=True - clean out all ansi/html markers and tokens
        """
        try:
            text = to_str(text if text else "", encoding=self.encoding)
        except Exception, e:
            self.sendLine(str(e))
        if "oob" in kwargs:
            oobstruct = self.sessionhandler.oobstruct_parser(kwargs.pop("oob"))
            self.sendLine("OOB" + json.dumps(oobstruct))
        raw = kwargs.get("raw", False)
        nomarkup = kwargs.get("nomarkup", False)
        if raw:
            self.sendLine(text)
        else:
            self.sendLine(parse_html(text, strip_ansi=nomarkup))
