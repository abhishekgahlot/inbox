""" ZeroRPC interface to syncing. """
import platform

from inbox.contacts.remote_sync import ContactSync
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import Account

from inbox.mailsync.backends import module_registry


class SyncService(object):
    def __init__(self):
        self.monitor_cls_for = {mod.PROVIDER: getattr(
            mod, mod.SYNC_MONITOR_CLS) for mod in module_registry.values()
            if hasattr(mod, 'SYNC_MONITOR_CLS')}

        self.log = get_logger()
        self.monitors = dict()
        self.contact_sync_monitors = dict()

        # Restart existing active syncs.
        # (Later we will want to partition these across different machines!)
        with session_scope() as db_session:
            # XXX: I think we can do some sqlalchemy magic to make it so we
            # can query on the attribute sync_enabled.
            for account_id, in db_session.query(Account.id).filter(
                    ~Account.sync_host.is_(None)):
                self.start_sync(account_id)

    def start_sync(self, account_id=None):
        """
        Starts all syncs if account_id not specified.
        If account_id doesn't exist, does nothing.

        """
        results = {}
        if account_id:
            account_id = int(account_id)
        with session_scope() as db_session:
            query = db_session.query(Account)
            if account_id is not None:
                query = query.filter_by(id=account_id)
            fqdn = platform.node()
            for acc in query:
                if acc.provider not in self.monitor_cls_for:
                    self.log.info('Inbox does not currently support {0}\
                        '.format(acc.provider))
                    continue

                self.log.info('Starting sync for account {0}'.format(
                    acc.email_address))

                if acc.sync_host is not None and acc.sync_host != fqdn:
                    results[acc.id] = \
                        'acc {0} is syncing on host {1}'.format(
                            acc.email_address, acc.sync_host)

                elif acc.id not in self.monitors:
                    try:
                        acc.sync_lock()

                        monitor = self.monitor_cls_for[acc.provider](
                            acc.id, acc.namespace.id, acc.email_address,
                            acc.provider)
                        self.monitors[acc.id] = monitor
                        monitor.start()
                        # For Gmail accounts, also start contacts sync
                        if acc.provider == 'gmail':
                            contact_sync = ContactSync(acc.id)
                            self.contact_sync_monitors[acc.id] = contact_sync
                            contact_sync.start()
                        acc.start_sync(fqdn)
                        db_session.add(acc)
                        db_session.commit()
                        results[acc.id] = 'OK sync started'
                    except Exception as e:
                        self.log.error(e.message)
                        results[acc.id] = 'ERROR error encountered: {0}'.\
                            format(e)
                else:
                    results[acc.id] = 'OK sync already started'

        if account_id:
            if account_id in results:
                return results[account_id]
            else:
                return 'OK no such user'
        return results

    def stop_sync(self, account_id=None):
        """
        Stops all syncs if account_id not specified.
        If account_id doesn't exist, does nothing.

        """
        results = {}
        if account_id:
            account_id = int(account_id)
        with session_scope() as db_session:
            query = db_session.query(Account)
            if account_id is not None:
                query = query.filter_by(id=account_id)
            fqdn = platform.node()
            for acc in query:
                if (not acc.id in self.monitors) or \
                        (not acc.sync_enabled):
                    results[acc.id] = 'OK sync stopped already'
                try:
                    if acc.sync_host is None:
                        results[acc.id] = 'Sync not running'
                        continue

                    assert acc.sync_host == fqdn, \
                        "sync host FQDN doesn't match: {0} <--> {1}" \
                        .format(acc.sync_host, fqdn)
                    # XXX Can processing this command fail in some way?
                    self.monitors[acc.id].inbox.put_nowait('shutdown')
                    acc.stop_sync()
                    db_session.add(acc)
                    db_session.commit()
                    acc.sync_unlock()
                    del self.monitors[acc.id]
                    # Also stop contacts sync (only relevant for Gmail
                    # accounts)
                    if acc.id in self.contact_sync_monitors:
                        del self.contact_sync_monitors[acc.id]
                    results[acc.id] = 'OK sync stopped'

                except Exception as e:
                    results[acc.id] = 'ERROR error encountered: {0}'.format(e)
        if account_id:
            if account_id in results:
                return results[account_id]
            else:
                return 'OK no such user'
        return results
