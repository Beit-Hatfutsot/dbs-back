#!/usr/bin/env python
# -*- coding: utf-8 -*-
from bhs_api import create_app


app, conf = create_app()


# following indexes are built to support bhs_api.fsearch functionality

for field in ["name_lc.0",
              "name_lc.1",
              "sex",
              "BIRT_PLAC_lc",
              "MARR_PLAC_lc",
              "tree_num",
              "DEAT_PLAC_lc",
              "marriage_years",
              "birth_year",
              "death_year",
              "archived",
              "sex",
              "tree_num",
              "deceased"]:
    print("creating field for {}".format(field))
    app.data_db.persons.create_index(field)
