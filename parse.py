from lxml import etree
from progressbar import ProgressBar, Percentage, Bar
from dateutil import parser, tz

import re
import unidecode
import datetime
import pytz
import requests
import os
import time
import codecs

DEBUG = False
FILENAME = 'my-wordpress-export.xml'

tree = etree.parse(FILENAME)
namespaces = tree.getroot().nsmap

def slugify(string):
    if string is not None:
        string = unidecode.unidecode(string).lower()
        return re.sub(r'\W+', '-', string)
    else:
        return ""

class Post:
    """ Ommitted from the XML standard:

            pubDate
            guid
            excerpt:encoded
            post_date_gmt
            post_type
            post_password
            is_sticky
    """
    def __init__(self, id=None, title=None):
        self.id = id
        self.title = title
        self.description = None
        self.creator = None
        self.body = None
        self.url = None
        self.post_date = datetime.datetime.now()
        self.comment_status = "open"
        self.ping_status = "open"
        self.slug = slugify(title)
        self.status = "publish"
        self.parent = None
        self.menu_order = 0
        self.tags = []
        self.categories = []
        self.comments = []

    def adjust_paths(self, attachments=None, prefix=''):
        if prefix is not '' and not prefix.endswith('/'):
            print "[ERRR] Your attachment prefix does not end in a trailing slash"
            return False
        if self.body is not None and attachments is not None:
            for attachment in attachments:
                if attachment.url in self.body:
                    new_url = prefix + attachment.url.split('/')[-1]
                    self.body = self.body.replace(attachment.url, new_url)
                    if DEBUG:
                        print "[DEBG] Replaced " + attachment.url + " with " + new_url

    def fix_paragraphs(self):
        fixed = self.body.replace('\n', '</p><p>')
        fixed = '<p>' + fixed + '</p>'
        fixed = fixed.replace('</p><p></p><p>', '</p><p>')
        self.body = fixed

    def fix_more(self):
        fixed = self.body.replace('<!--more-->', '[[MORE]]')
        self.body = fixed


class Attachment:
    def __init__(self, id=None, title=None, url=None):
        self.id = id
        self.title = title
        self.url = url

    def download(self, path='attachments'):
        if self.url is not None:
            title = self.url.split('/')[-1]
            attachment = requests.get(self.url)
            if attachment.status_code == requests.codes.ok:
                f = open(os.path.join(path, title), 'wb')
                f.write(attachment.content)
                f.close()
            else:
                attachment.raise_for_status()


def find_blog(tree):
    if tree.find(".//title") is not None:
        title = tree.find(".//title").text
        url = tree.find(".//link").text
        description = tree.find(".//description").text
        exported = tree.find(".//pubDate").text
        language = tree.find(".//language").text
        print "Found %s" % title


def find_authors(tree):
    author_elems = tree.findall(".//wp:author", namespaces=namespaces)
    authors = []
    for author_elem in author_elems:
        login = author_elem.find("./wp:author_login", namespaces=namespaces)
        email = author_elem.find("./wp:author_email", namespaces=namespaces)
        username = author_elem.find("./wp:author_display_name", namespaces=namespaces)
        first_name = author_elem.find("./wp:author_first_name", namespaces=namespaces)
        last_name = author_elem.find("./wp:author_last_name", namespaces=namespaces)
        authors.append({
            'login': login,
            'email': email,
            'username': username,
            'first_name': first_name,
            'last_name': last_name
        })
    if len(authors) > 0:
        print "Found %i authors" % len(authors)
        return authors
    else:
        print "[WARN] Found no authors!"
        return False


def find_tags(tree):
    tag_elems = tree.findall(".//wp:tag", namespaces=namespaces)
    tags = []
    for tag_elem in tag_elems:
        slug = tag_elem.find("./wp:tag_slug", namespaces=namespaces)
        name = tag_elem.find("./wp:tag_name", namespaces=namespaces)
        tags.append({
            'slug': slug,
            'name': name
        })
    if len(tags) > 0:
        print "Found %i tags" % len(tags)
        return tags
    else:
        print "[WARN] Found no tags!"
        return False

def find_posts(tree, published=True):
    if published:
        xpath = ".//item[wp:post_type='post' and wp:status='publish']"
        item_elems = tree.xpath(xpath, namespaces=namespaces)
    else:
        item_elems = tree.findall(".//item[wp:post_type='post']", namespaces=namespaces)
    posts = []
    for post_elem in item_elems:
        post = Post(unicode(post_elem.find("./wp:post_id", namespaces=namespaces).text), unicode(post_elem.find("./title").text))
        post.url = unicode(post_elem.find("./link").text)
        post.body = unicode(post_elem.find("./content:encoded", namespaces=namespaces).text)
        post_stamp = parser.parse(post_elem.find("./wp:post_date", namespaces=namespaces).text)
        local = pytz.timezone("America/Chicago")
        local_stamp = local.localize(post_stamp, is_dst=None)
        utc_stamp = local_stamp.astimezone(pytz.utc)
        post.post_date = utc_stamp
        tag_elems = post_elem.xpath("./category[@domain='post_tag']")
        tags = []
        if tag_elems is not None:
            for tag in tag_elems:
                tags.append(tag.get('nicename'))
        post.tags = tags
        posts.append(post)

    if len(posts) > 0:
        print "Found %i posts" % len(posts)
        return posts
    else:
        print "[WARN] Found no posts!"
        return False


def find_attachments(tree, download=True):
    xpath = ".//item[wp:post_type='attachment']"
    attachment_elems = tree.xpath(xpath, namespaces=namespaces)
    attachments = []
    for attachment_elem in attachment_elems:
        attachment = Attachment(attachment_elem.find("./wp:post_id", namespaces=namespaces).text, unicode(attachment_elem.find("./title").text), attachment_elem.find("./wp:attachment_url", namespaces=namespaces).text)
        attachments.append(attachment)


    if len(attachments) > 0:
        print "Found %i attachments" % len(attachments)
        if download:
            print "Downloading %i attachments" % len(attachments)
            progress = ProgressBar(widgets=[Percentage(), Bar()], maxval=len(attachments)).start()
            for i, attachment in enumerate(attachments):
                attachment.download('attachments')
                progress.update(i)
            progress.finish()
            print "Downloaded %i attachments" % len(attachments)
        return attachments
    else:
        print "[WARN] Found no attachments!"
        return False
