# TibiaWikiTools
Collection of scripts and tasks to do automatic updates or maintenance to TibiaWiki.

## Configuration

Two files must be created in the root directory in order to run this.

### user-config.py
This file defines the wiki definition to be used.

```python
family = 'tibiawiki'
mylang = 'en'
usernames['tibiawiki']['en'] = 'Username'
password_file = 'user-password.py'
```

### user-password.py
The credentials to use.

```python
("Username", BotPassword("BotUser", "Token"))
```