
import dbus.glib
import gobject
import sys

from account import read_account, connect

from telepathy.client.channel import Channel
from telepathy.constants import (
    CONNECTION_HANDLE_TYPE_CONTACT, CONNECTION_STATUS_CONNECTED,
    CONNECTION_STATUS_DISCONNECTED)
from telepathy.interfaces import (
    CHANNEL_INTERFACE, CHANNEL_INTERFACE_GROUP, CHANNEL_TYPE_STREAMED_MEDIA,
    CONN_INTERFACE)

class StreamedMediaChannel(Channel):
    def __init__(self, ready_callback, bus_name, object_path):
        self.ready_callback = ready_callback
        Channel.__init__(self, bus_name, object_path)

    def got_interfaces(self):
        self.ready_callback(self)

class Call:
    def __init__(self, conn, contact):
        self.conn = conn
        self.contact = contact
        self.channel = None

        conn[CONN_INTERFACE].connect_to_signal('StatusChanged',
            self.status_changed_cb)
        conn[CONN_INTERFACE].connect_to_signal('NewChannel',
            self.new_channel_cb)

    def run(self):
        self.loop = gobject.MainLoop()

        try:
            self.loop.run()
        except KeyboardInterrupt:
            print "killed"

            if self.channel:
                self.channel.Close()

    def quit(self):
        if self.loop:
            self.loop.quit()
            self.loop = None

    def status_changed_cb(self, state, reason):
        if state == CONNECTION_STATUS_CONNECTED:
            handle = conn[CONN_INTERFACE].RequestHandle(
                CONNECTION_HANDLE_TYPE_CONTACT, self.contact)

            print 'got handle %d for %s' % (handle, self.contact)

            # hack
            import time
            time.sleep(5)

            conn[CONN_INTERFACE].RequestChannel(
                CHANNEL_TYPE_STREAMED_MEDIA, CONNECTION_HANDLE_TYPE_CONTACT,
                handle, True,
                reply_handler=lambda *stuff: None,
                error_handler=self.request_channel_error_cb)
        elif state == CONNECTION_STATUS_DISCONNECTED:
            print 'connection closed'
            self.quit()

    def request_channel_error_cb(self, exception):
        print 'error:', exception
        self.quit()

    def new_channel_cb(self, object_path, channel_type, handle_type, handle,
            suppress_handler):
        if channel_type != CHANNEL_TYPE_STREAMED_MEDIA:
            return

        self.chan_handle_type = handle_type
        self.chan_handle = handle

        print "new streamed media channel"
        channel = StreamedMediaChannel(
            self.channel_ready_cb, self.conn._dbus_object._named_service,
            object_path)

    def channel_ready_cb(self, channel):
        print "channel ready"
        channel[CHANNEL_INTERFACE].connect_to_signal('Closed', self.closed_cb)
        channel[CHANNEL_INTERFACE_GROUP].connect_to_signal('MembersChanged',
            self.members_changed_cb)

        bus = dbus.Bus()
        stream_engine = bus.get_object(
            'org.freedesktop.Telepathy.VoipEngine',
            '/org/freedesktop/Telepathy/VoipEngine')
        handler = dbus.Interface(stream_engine,
            'org.freedesktop.Telepathy.ChannelHandler')
        handler.HandleChannel(
            self.conn._dbus_object._named_service,
            self.conn._dbus_object._object_path,
            CHANNEL_TYPE_STREAMED_MEDIA,
            channel._dbus_object._object_path,
            self.chan_handle_type,
            self.chan_handle)

    def closed_cb(self):
        print "channel closed"
        self.quit()

    def members_changed_cb(self, message, added, removed, local_pending,
            remote_pending):
        print 'MembersChanged', (
            added, removed, local_pending, remote_pending)

if __name__ == '__main__':
    assert len(sys.argv) == 3
    account_file = sys.argv[1]
    contact = sys.argv[2]

    manager, protocol, account = read_account(account_file)
    conn = connect(manager, protocol, account)
    call = Call(conn, contact)
    call.run()
    conn[CONN_INTERFACE].Disconnect()

