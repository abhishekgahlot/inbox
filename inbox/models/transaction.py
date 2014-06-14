import itertools
import os
import re
import json

from hashlib import sha256
from datetime import datetime
import bson

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime, Boolean,
                        Enum, ForeignKey, Text, func, event, and_, or_, asc,
                        desc)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import (reconstructor, relationship, backref, deferred,
                            validates, object_session)
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import BLOB
from sqlalchemy.sql.expression import true, false

from inbox.log import get_logger
log = get_logger()

from inbox.config import config
from inbox.sqlalchemy_ext.util import generate_public_id
from inbox.util.encoding import base36decode
from inbox.util.file import Lock, mkdirp
from inbox.util.html import (plaintext2html, strip_tags, extract_from_html,
                             extract_from_plain)
from inbox.util.misc import load_modules
from inbox.util.cryptography import encrypt_aes, decrypt_aes
from inbox.sqlalchemy_ext.util import (JSON, BigJSON, Base36UID,
                                       maybe_refine_query)
from inbox.sqlalchemy_ext.revision import Revision, gen_rev_role
from inbox.basicauth import AUTH_TYPES

from inbox.models.roles import Blob
from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID 
from inbox.models.namespace import Namespace 

class Transaction(MailSyncBase, Revision, HasPublicID):


    """ Transactional log to enable client syncing. """
    # Do delete transactions if their associated namespace is deleted.
    namespace_id = Column(Integer,
                          ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(
        Namespace,
        primaryjoin='and_(Transaction.namespace_id == Namespace.id, '
                    'Namespace.deleted_at.is_(None))')

    object_public_id = Column(String(191), nullable=True)

    # The API representation of the object at the time the transaction is
    # generated.
    public_snapshot = Column(BigJSON)
    # Dictionary of any additional properties we wish to snapshot when the
    # transaction is generated.
    private_snapshot = Column(BigJSON)

    def set_extra_attrs(self, obj):
        try:
            self.namespace = obj.namespace
        except AttributeError:
            log.info("Couldn't create {2} revision for {0}:{1}".format(
                self.table_name, self.record_id, self.command))
            log.info("Delta is {0}".format(self.delta))
            log.info("Thread is: {0}".format(obj.thread_id))
            raise
        object_public_id = getattr(obj, 'public_id', None)
        if object_public_id is not None:
            self.object_public_id = object_public_id

    def take_snapshot(self, obj):
        """Record the API's representation of `obj` at the time this
        transaction is generated, as well as any other properties we want to
        have available in the transaction log. Used for client syncing and
        webhooks."""
        from inbox.models.kellogs import APIEncoder
        encoder = APIEncoder()
        self.public_snapshot = encoder.default(obj)

        if obj.__class__.__name__ == 'Message':  # hack
            self.private_snapshot = {
                'recentdate': obj.thread.recentdate,
                'subjectdate': obj.thread.subjectdate,
                'filenames': [part.filename for part in obj.parts if
                              part.is_attachment]}


# class HasRevisions(object):
#     """ Generic mixin which creates a read-only revisions attribute on the
#         class for convencience.
#     """
#     @declared_attr
#     def revisions(cls):
#         return relationship('transaction',
#                             primaryjoin="{0}.id==transaction.record_id".format(
#                                 cls.__name__),
#                             foreign_keys='transaction.record_id', viewonly=True)


from inbox.models.transaction import Transaction

HasRevisions = gen_rev_role(Transaction)
