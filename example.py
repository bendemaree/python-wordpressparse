from parse import *

blogs = find_blog(tree)
authors = find_authors(tree)
tags = find_tags(tree)
posts = find_posts(tree)
attachments = find_attachments(tree, download=False)

for post in posts:
    post.adjust_paths(attachments=attachments, prefix='http://assets.mysite.com/img/')
    post.fix_paragraphs()
    post.fix_more()
