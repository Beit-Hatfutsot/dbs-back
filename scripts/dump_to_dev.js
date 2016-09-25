// js script to remove details of the living
db.genTreeIndividuals.update({GTN: 3372, "tree.deceased": false},
       {"$set": {BD:"",BP:"",MD:"",MP:""},
        "$unset": {"tree.BIRT_DATE":1, "tree.MARR_PLAC":1,
                 "tree.MARR_DATE":1, "tree.OCCU":1,
                 "tree.NOTE":1, "tree.BIRT_PLAC":1}},
                {multi:true});
