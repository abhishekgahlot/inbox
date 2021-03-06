from datetime import datetime

from inbox.models.session import session_scope
from inbox.models.account import Account


def report_stopped(account_id, folder_name=None):
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)

        # MailSyncMonitor for account
        if folder_name is None:
            account.stop_sync()
        else:
            # FolderSyncMonitor for account's folder
                for f in account.foldersyncstatuses:
                    if f.folder.name == folder_name:
                        f.update_metrics(
                            dict(run_state='stopped',
                                 sync_end_time=datetime.utcnow()))

        db_session.commit()


def report_killed(account_id, folder_name=None):
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)

        # MailSyncMonitor for account
        if folder_name is None:
            account.kill_sync()
        else:
            # FolderSyncMonitor for account's folder
                for f in account.foldersyncstatuses:
                    if f.folder.name == folder_name:
                        f.update_metrics(
                            dict(run_state='killed',
                                 sync_end_time=datetime.utcnow()))

        db_session.commit()
