#!/usr/bin/env python

import dbus
import dbus.service
if getattr(dbus, 'version', (0,0,0)) >= (0,41,0):
    import dbus.glib
import gobject
import xmpp

CONN_MGR_INTERFACE = 'org.freedesktop.ipcf.ConnectionManager'
CONN_MGR_OBJECT = '/org/freedesktop/ipcf/ConnectionManager'
CONN_MGR_SERVICE = 'org.freedesktop.ipcf.ConnectionManager'

CONN_INTERFACE = 'org.freedesktop.ipcf.Connection'
CONN_OBJECT = '/org/freedesktop/ipcf/Connection'
CONN_SERVICE = 'org.freedesktop.ipcf.Connection'

CHANNEL_INTERFACE = 'org.freedesktop.ipcf.Channel'
TEXT_CHANNEL_INTERFACE = 'org.freedesktop.ipcf.TextChannel'

class JabberChannel(dbus.service.Object):
    count = 0

    def __init__(self, conn):
        self.conn = conn
        self.object_path = self.conn.object_path+'/channel'+str(JabberChannel.count)
        JabberChannel.count += 1
        dbus.service.Object.__init__(self, self.conn.bus_name, self.object_path)

    @dbus.service.method(CHANNEL_INTERFACE)
    def Close(self):
        pass

    @dbus.service.signal(CHANNEL_INTERFACE)
    def Closed(self):
        pass

    @dbus.service.method(CHANNEL_INTERFACE)
    def GetType(self):
        if self.type == '':
            raise IOError('Channel type not defined!')

        return self.type

class JabberTextChannel(JabberChannel):
    def __init__(self, conn, interfaces):
        JabberChannel.__init__(self, conn)

        self.msgid = 0
        self.type = TEXT_CHANNEL_INTERFACE

        for i in interfaces.keys():
            if i == 'recipient':
                self.recipient = interfaces[i]
            print i, interfaces[i]

    def send_callback(self, id, text):
        msg = xmpp.protocol.Message(self.recipient, text)
        self.conn.client.send(msg)
        self.Sent(id, text)

    @dbus.service.method(TEXT_CHANNEL_INTERFACE)
    def Send(self, text):
        id = self.msgid
        self.msgid += 1
        gobject.idle_add(self.send_callback, id, text)
        return id

    @dbus.service.signal(TEXT_CHANNEL_INTERFACE)
    def Sent(self, id, text):
        pass

    @dbus.service.signal(TEXT_CHANNEL_INTERFACE)
    def Recieved(self, text):
        pass

class JabberConnection(dbus.service.Object):
    def __init__(self, manager, account, conn_info):
        self.jid = xmpp.protocol.JID(account)
        if self.jid.getResource() == '':
            self.jid.setResource('IPCF')

        self.service_name = '.'.join((CONN_SERVICE, 'jabber', self.jid.getDomain(), self.jid.getNode(), self.jid.getResource()))
        self.object_path = '/'.join((CONN_OBJECT, 'jabber', self.jid.getDomain(), self.jid.getNode(), self.jid.getResource()))
        self.bus_name = dbus.service.BusName(self.service_name, bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, self.bus_name, self.object_path)

        self.channels = []
        self.manager = manager
        self.password = conn_info['password']

        if conn_info.has_key('server'):
            if conn_info.has_key('port'):
                self.client = xmpp.client.Client(conn_info['server'], conn_info['port'])
            else:
                self.client = xmpp.client.Client(conn_info['server'])
        else:
            if conn_info.has_key('port'):
                self.client = xmpp.client.Client(self.jid.getDomain(), conn_info['port'])
            else:
                self.client = xmpp.client.Client(self.jid.getDomain())

        gobject.idle_add(self.connect)

    def connect(self):
        self.StatusChanged('connecting')

        if not self.client.connect():
            self.StatusChange('disconnected')

        if not self.client.auth(self.jid.getNode(), self.password, self.jid.getResource()):
            self.StatusChanged('disconnected')

        self.client.RegisterDisconnectHandler(self.disconnectHandler)
        self.client.RegisterHandler('iq', self.iqHandler)
        self.client.RegisterHandler('message', self.messageHandler)
        self.client.RegisterHandler('presence', self.presenceHandler)
        self.client.sendInitPresence()

        self.StatusChanged('connected')

        gobject.idle_add(self.poll)

        return False # run once

    def poll(self):
        if self.client.isConnected():
            self.client.Process(0.01)
            return True # keep running
        else:
            return False # stop running

    def disconnectHandler(self):
        if self.die:
            self.StatusChanged('disconnected')
        else:
            self.StatusChanged('connecting')
            self.client.reconnectAndReauth()

    def iqHandler(self, conn, node):
        pass

    def messageHandler(self, conn, node):
        pass

    def presenceHandler(self, conn, node):
        pass

    @dbus.service.signal(CONN_INTERFACE)
    def StatusChanged(self, status):
        print 'service_name: %s object_path: %s signal: StatusChanged %s' % (self.service_name, self.object_path, status)
        self.status = status

    @dbus.service.method(CONN_INTERFACE)
    def GetStatus(self):
        return self.status

    @dbus.service.method(CONN_INTERFACE)
    def Disconnect(self):
        print "Disconnect called"
        self.die = True
        self.client.disconnect()

    @dbus.service.signal(CONN_INTERFACE)
    def NewChannel(self, type, object_path):
        print 'service_name: %s object_path: %s signal: NewChannel %s %s' % (self.service_name, self.object_path, type, object_path)

    @dbus.service.method(CONN_INTERFACE)
    def ListChannels(self):
        ret = []
        for channel in self.channels:
            ret.append(channel.object_path)
        return ret

    @dbus.service.method(CONN_INTERFACE)
    def RequestChannel(self, type, interfaces):
        if type == TEXT_CHANNEL_INTERFACE:
            channel = JabberTextChannel(self, interfaces)
            self.channels.append(channel)
            self.NewChannel(type, channel.object_path)
            return channel.object_path
        else:
            raise IOError('Unknown channel type %s' % type)

class JabberConnectionManager(dbus.service.Object):
    def __init__(self):
        self.bus_name = dbus.service.BusName(CONN_MGR_SERVICE+'.cheddar', bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, self.bus_name, CONN_MGR_OBJECT+'/cheddar')

        self.connections = []
        self.protos = set(['jabber'])

    @dbus.service.method(CONN_MGR_INTERFACE)
    def ListProtocols(self):
        return self.protos

    @dbus.service.method(CONN_MGR_INTERFACE)
    def Connect(self, proto, account, connect_info):
        if proto in self.protos:
            conn = JabberConnection(self, account, connect_info)
            self.connections.append(conn)
            return (conn.service_name, conn.object_path)
        else:
            raise IOError('Unknown protocol %s' % (proto))

if __name__ == '__main__':
    manager = JabberConnectionManager()
    mainloop = gobject.MainLoop()
    mainloop.run()
