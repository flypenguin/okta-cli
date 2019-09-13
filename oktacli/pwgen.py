from pkg_resources import resource_filename

from pony.orm import Database, Required, db_session

# resources:
#   * https://github.com/ponyorm/pony/issues/33
#   * https://stackoverflow.com/a/24591688/902327


db = Database()


class Word(db.Entity):
    lang = Required(str)
    word = Required(str)


def generate_password(num_words=3, lang="en"):
    sqlfile = resource_filename("oktacli", "wordlist.sqlite")
    db.bind("sqlite", sqlfile)
    db.generate_mapping(create_tables=True)
    with db_session:
        rv = [p.word
              for p in Word.select(lambda x: x.lang == lang).random(num_words)]
    return rv
