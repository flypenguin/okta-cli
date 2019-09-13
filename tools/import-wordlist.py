#!/usr/bin/env python3

from pony.orm import Database, Required, db_session, delete

from argparse import ArgumentParser


db = Database()


class Word(db.Entity):
    lang = Required(str)
    word = Required(str)


def doit():
    parser = ArgumentParser()
    parser.add_argument("-d", "--database", required=True)
    parser.add_argument("-f", "--wordsfile", required=True)
    parser.add_argument("-l", "--language", required=True)
    config = parser.parse_args()

    db.bind("sqlite", filename=config.database, create_db=True)
    db.generate_mapping(create_tables=True)
    with open(config.wordsfile, "r") as wordsfile:
        with db_session:
            # delete all LANG words from database
            delete(w for w in Word if w.lang == config.language)
            # import new wordlist for language
            for word in wordsfile.readlines():
                Word(lang=config.language, word=word)


if __name__ == "__main__":
    doit()
