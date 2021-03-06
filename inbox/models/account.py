from datetime import datetime

from sqlalchemy import (Column, Integer, String, DateTime, Boolean, ForeignKey,
                        Enum)
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import true

from inbox.util.file import Lock

from inbox.models.mixins import HasPublicID
from inbox.models.base import MailSyncBase
from inbox.models.folder import Folder
from inbox.models.base import MAX_INDEXABLE_LENGTH


class Account(MailSyncBase, HasPublicID):
    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_identity': 'account',
                       'polymorphic_on': discriminator}

    # http://stackoverflow.com/questions/386294
    email_address = Column(String(MAX_INDEXABLE_LENGTH),
                           nullable=True, index=True)

    @property
    def provider(self):
        """ A constant, unique lowercase identifier for the account provider
        (e.g., 'gmail', 'eas'). Subclasses should override this.

        We prefix provider folders with this string when we expose them as
        tags through the API. E.g., a 'jobs' folder/label on a Gmail
        backend is exposed as 'gmail-jobs'. Any value returned here
        should also be in Tag.RESERVED_PROVIDER_NAMES.

        """
        raise NotImplementedError

    # local flags & data
    save_raw_messages = Column(Boolean, server_default=true())

    last_synced_contacts = Column(DateTime, nullable=True)

    # Folder mappings for the data we sync back to the account backend.  All
    # account backends will not provide all of these. This may mean that Inbox
    # creates some folders on the remote backend, for example to provide
    # "archive" functionality on non-Gmail remotes.
    inbox_folder_id = Column(Integer,
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    inbox_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.inbox_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')
    sent_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    sent_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.sent_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    drafts_folder_id = Column(Integer,
                              ForeignKey(Folder.id, ondelete='SET NULL'),
                              nullable=True)
    drafts_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.drafts_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    spam_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    spam_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.spam_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    trash_folder_id = Column(Integer,
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    trash_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.trash_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    archive_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    archive_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.archive_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    all_folder_id = Column(Integer,
                           ForeignKey(Folder.id, ondelete='SET NULL'),
                           nullable=True)
    all_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.all_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    starred_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    starred_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.starred_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    important_folder_id = Column(Integer,
                                 ForeignKey(Folder.id, ondelete='SET NULL'),
                                 nullable=True)
    important_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.important_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    sync_host = Column(String(255), nullable=True)
    sync_state = Column(Enum('running', 'stopped', 'killed'), nullable=True)
    sync_start_time = Column(DateTime, nullable=True)
    sync_end_time = Column(DateTime, nullable=True)

    @property
    def sync_enabled(self):
        return self.sync_host is not None

    def start_sync(self, sync_host):
        self.sync_host = sync_host
        self.sync_start_time = datetime.utcnow()
        self.sync_end_time = None

        self.sync_state = 'running'

    def stop_sync(self):
        self.sync_host = None
        self.sync_end_time = datetime.utcnow()

        self.sync_state = 'stopped'

    def kill_sync(self):
        # Don't change sync_host if moving to state 'killed'
        self.sync_end_time = datetime.utcnow()

        self.sync_state = 'killed'

    @property
    def sync_status(self):
        return dict(id=self.id,
                    email=self.email_address,
                    provider=self.provider,
                    is_enabled=self.sync_enabled,
                    state=self.sync_state,
                    sync_start_time=self.sync_start_time,
                    sync_end_time=self.sync_end_time)

    @property
    def sender_name(self):
        # Used for setting sender information when we send a message.
        # Can be overridden by subclasses that store account name information.
        return ''

    @classmethod
    def _get_lock_object(cls, account_id, lock_for=dict()):
        """ Make sure we only create one lock per account per process.

        (Default args are initialized at import time, so `lock_for` acts as a
        module-level memory cache.)
        """
        return lock_for.setdefault(account_id,
                                   Lock(cls._sync_lockfile_name(account_id),
                                        block=False))

    @classmethod
    def _sync_lockfile_name(cls, account_id):
        return "/var/lock/inbox_sync/{}.lock".format(account_id)

    @property
    def _sync_lock(self):
        return self._get_lock_object(self.id)

    def sync_lock(self):
        """ Prevent mailsync for this account from running more than once. """
        self._sync_lock.acquire()

    def sync_unlock(self):
        self._sync_lock.release()

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator,
                       'polymorphic_identity': 'account'}
