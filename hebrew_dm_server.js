#!/usr/bin/env node

var ALEF = 'א'; // d7 90
var BAIS = 'ב'; // d7 91
var GIMEL = 'ג'; // d7 92
var DALET = 'ד'; // d7 93
var HAY = 'ה'; // d7 94
var VAV = 'ו'; // d7 95
var ZAYIN = 'ז'; // d7 96
var KHESS = 'ח'; // d7 97
var TESS = 'ט'; // d7 98
var YUD = 'י'; // d7 99
var KHAF2 = 'ך'; // d7 9a
var KAF = 'כ'; // d7 9b
var LAMED = 'ל'; // d7 9c
var MEM2 = 'ם'; // d7 9d
var MEM = 'מ'; // d7 9e
var NUN2 = 'ן'; // d7 9f
var NUN = 'נ'; // d7 a0
var SAMEKH = 'ס'; // d7 a1
var AYIN = 'ע'; // d7 a2
var FAY2 = 'ף'; // d7 a3
var PAY = 'פ'; // d7 a4
var TSADI2 = 'ץ'; // d7 a5
var TSADI = 'צ'; // d7 a6
var KUF = 'ק'; // d7 a7
var RAISH = 'ר'; // d7 a8
var SHIN = 'ש'; // d7 a9
var TAF = 'ת'; // d7 aa
var BLANK = ' ';
var GERESH = '׳';


var firstLetter = ALEF;
var lastLetter = TAF;
var vowels = ALEF + AYIN + VAV;

var newrules = [
[ZAYIN + DALET + ZAYIN, "2", "4", "4"],
[SAMEKH + TESS + SHIN, "2", "4", "4"],
[SAMEKH + TESS + ZAYIN, "2", "4", "4"],
[SAMEKH + TAF + ZAYIN, "2", "4", "4"],
[SAMEKH + TAF + SHIN, "2", "4", "4"],
[SHIN + TESS + SHIN, "2", "4", "4"],
[SHIN + TESS + ZAYIN, "2", "4", "4"],
[SHIN + TAF + SHIN, "2", "4", "4"],
[SHIN + TAF + ZAYIN, "2", "4", "4"],
[YUD + YUD + AYIN, "1", "1", "1"],
[YUD + YUD + HAY, "1", "1", "1"],
[DALET + SAMEKH, "4", "4", "4"],
[DALET + SHIN, "4", "4", "4"],
[DALET + ZAYIN, "4", "4", "4"],
[KHESS + SAMEKH, "5", "54", "54"],
[TESS + SHIN, "4", "4", "4"],
[KHESS + SHIN, "5", "54", "54"],
[KAF + SAMEKH, "5", "54", "54"],
[KAF + SHIN, "5", "54", "54"],
[MEM + NUN, "66", "66", "66"],
[MEM + NUN2, "66", "66", "66"],
[NUN + MEM, "66", "66", "66"],
[NUN + MEM2, "66", "66", "66"],
[PAY + BAIS, "7", "7", "7"], // give me an example
[KUF + SAMEKH, "5", "54", "54"],
[KUF + SHIN, "5", "54", "54"],
[SAMEKH + DALET, "2", "43", "43"],
[SAMEKH + TESS, "2", "43", "43"],
[SAMEKH + TAF, "2", "43", "43"],
[SHIN + DALET, "2", "43", "43"],
[SHIN + TESS, "2", "43", "43"],
[SHIN + TAF, "2", "43", "43"],
[TAF + SHIN, "4", "4", "4"],
[ZAYIN + SHIN, "4", "4", "4"],
[ALEF + VAV, "0", "7", "999"],
[YUD + VAV, "1", "999", "999"],
[YUD + ALEF, "1", "1", "1"],
[ALEF, "0", "999", "999"],
[BAIS, "7", "7", "7"],
[GIMEL, "5", "5", "5"],
[DALET, "3", "3", "3"],
[HAY, "5", "5", "999"],
[VAV, "7", "7", "7"],
[ZAYIN, "4", "4", "4"],
[KHESS, "5", "5", "5"],
[TESS, "3", "3", "3"],
[YUD, "1", "1", "999"],
[KAF, "5", "5", "5"],
[KHAF2, "5", "5", "5"],
[LAMED, "8", "8", "8"],
[MEM, "6", "6", "6"],
[MEM2, "6", "6", "6"],
[NUN, "6", "6", "6"],
[NUN2, "6", "6", "6"],
[SAMEKH, "4", "4", "4"],
[AYIN, "0", "999", "999"],
[PAY, "7", "7", "7"],
[FAY2, "7", "7", "7"],
[TSADI, "4", "4", "4"],
[TSADI2, "4", "4", "4"],
[KUF, "5", "5", "5"],
[RAISH, "9", "9", "9"],
[SHIN, "4", "4", "4"],
[TAF, "3", "3", "3"],
];

var xnewrulesSephardic = [
[YUD + ALEF, "1", "999", "999"],
[YUD + VAV, "1", "1", "1"],
[VAV, "7", "999", "999"], // vowel VAV can never appear at the beginning of a word
];
var xnewruleslistSephardic = "!" + YUD + ALEF + "!" + YUD + VAV + "!" + VAV + "!!";
var xnewrules = xnewrulesSephardic;
var xnewruleslist = xnewruleslistSephardic;

// (c) Stephen P. Morse, 2003

var SEPARATOR = " ";
var GROUPSEPARATOR = " ";

// provide alternate entry point so that dm.js and soundex.js can be called the same way
function getSoundex(MyStr) {
  return soundex(MyStr);
}

function soundex(MyStr) {

  // replace certain text in strings with a slash
  var re = / v | v\. | vel | aka | f | f. | r | r. | false | recte | on zhe /gi;
  MyStr = MyStr.replace(re, '/');

  // append soundex of each individual word
  var result = "";
  var MyStrArray = MyStr.split(/[\s|,]+/); // use space or comma as token delimiter
  for (var i in MyStrArray) {
    if (MyStrArray[i].length > 0) { // ignore null at ends of array (due to leading or trailing space)
      if (i != 0) {
        result += GROUPSEPARATOR;
      }
      result += soundex2(MyStrArray[i]);
    }
  }
  return result;
}

function soundex2(MyStr) {
  MyStr = MyStr.toLowerCase();
  var MyStr3 = MyStr;

  dm3 = "";
  while (MyStr3.length > 0) {
    MyStr2 = "";
    LenMyStr3 = MyStr3.length;

    for (i=0; i < MyStr3.length; i++) {
      if ((MyStr3.charAt(i) >= firstLetter && MyStr3.charAt(i) <= lastLetter) || MyStr3.charAt(i) == '/') {
        if (MyStr3.charAt(i) == '/') {
          MyStr3 = MyStr3.slice(i + 1);
          break;
        } else {
          MyStr2 = MyStr2 + MyStr3.charAt(i);
        }
      } else {
        if (MyStr[i] == "(" || MyStr[i] == SEPARATOR) {
          break;
        }
      }
    }
    if (i == LenMyStr3) {
      MyStr3 = ""; // finished
    }

    MyStr = MyStr2;
    dm = "";
    var allblank = true;
    for (k=0; k<MyStr.length; k++) {
      if (MyStr.charAt[k] != ' ') {
        allblank = false;
        break;
      }
    }
    if (!allblank) {

      dim_dm2 = 1;
      dm2 = new Array(16);
      dm2[0] = "";

      first = 1;
      lastdm = new Array(16);
      lastdm[0] = "";

      while (MyStr.length > 0) {

        for (i=0; i<newrules.length; i++) { // loop through the rules
          if (MyStr.slice(0, newrules[i][0].length) == newrules[i][0]) { // match found
            //check for xnewrules branch
            xr = "!" + newrules[i][0] + "!";
            if (xnewruleslist.indexOf(xr) != -1) {
              xr = xnewruleslist.indexOf(xr) / 3;
              for (dmm = dim_dm2; dmm < 2 * dim_dm2; dmm++) {
                dm2[dmm] = dm2[dmm - dim_dm2];
                lastdm[dmm] = lastdm[dmm - dim_dm2];
              }
              dim_dm2 = 2 * dim_dm2;
            } else {
              xr = -1;
            }
   
            dm = dm + "_" + newrules[i][0];
            if (MyStr.length > newrules[i][0].length) {
              MyStr = MyStr.slice(newrules[i][0].length);
            } else {
              MyStr = "";
            }

            if (first == 1) {
              dm2[0] = newrules[i][1];
              first = 0;
              lastdm[0] = newrules[i][1];

              if (xr >= 0) {
                dm2[1] = xnewrules[xr][1];
                lastdm[1] = xnewrules[xr][1];

              }
            } else {
              dmnumber = 1;
              if (dim_dm2 > 1) {
                dmnumber = dim_dm2 / 2;
              }
              if (MyStr.length > 0 && vowels.indexOf(MyStr.charAt(0)) != -1) { // followed by a vowel
                for (ii=0; ii<dmnumber; ii++) {
                  if (newrules[i][2] != "999" && newrules[i][2] != lastdm[ii]) {
                    // vowel following, non-branching case, not a vowel and different code from previous one
                    lastdm[ii] = newrules[i][2];
                    dm2[ii] += newrules[i][2];
                  } else if (newrules[i][3] == 999) { // should this be newrules[i][2] ?
                    // vowel following, non-branching case, is a vowel, so reset previous one to blank
                    lastdm[ii] = "";
                  }
                  // else non-branching case, not a vowel and same code from previous one -- do nothing
                }

                if (dim_dm2 > 1) {
                  for (ii=dmnumber; ii<dim_dm2; ii++) {
                    if (xr >= 0 && xnewrules[xr][2] != "999" && xnewrules[xr][2] != lastdm[ii]) {
                      // vowel following, branching case, not a vowel and different code from prevous case
                      lastdm[ii] = xnewrules[xr][2];
                      dm2[ii] += xnewrules[xr][2];

                    // not in original code -- added for dm hebrew, never encountered used in dm latin
                    // occurs only when a vowel is in the branching case (e.g., the VAV in hebrew)
                    } else if (xr >= 0 && xnewrules[xr][2] == "999") {
                      // vowel following, branching case, is a vowel, so reset previous one to blank
                      lastdm[ii] = "";

                    } else {
                      if (xr < 0 && newrules[i][2] != "999" && newrules[i][2] != lastdm[ii]) {
                        // vowel following, non-branching case, not a vowel and different code from prevous case
                        lastdm[ii] = newrules[i][2];
                        dm2[ii] += newrules[i][2];
                      } else if (newrules[i][3] == 999) { // should this be newrules[i][2] ?
                        // vowel following, non-branching case, is a vowel, so reset previous one to blank
                        lastdm[ii] = "";
                      }
                    }
                  }
                }
      
              } else {
                for (ii=0; ii<dmnumber; ii++) {
                  if (newrules[i][3] != "999" && newrules[i][3] != lastdm[ii]) {
                    // non-branching case, not a vowel and different code from prevous case
                    lastdm[ii] = newrules[i][3];
                    dm2[ii] += newrules[i][3];
                  } else if (newrules[i][3] == 999) {
                    // non-branching case, is a vowel, so reset previous one to blank
                    lastdm[ii] = "";
                  }
                  // else non-branching case, not a vowel and same code from previous one -- do nothing
                }
                if (dim_dm2 > 1) {
                  for (ii=dmnumber; ii<dim_dm2; ii++) {
                    if (xr >= 0 && xnewrules[xr][3] != "999" && xnewrules[xr][3] != lastdm[ii]) {
                      // branching case, not a vowel and different code from prevous case
                      lastdm[ii] = xnewrules[xr][3];
                      dm2[ii] += xnewrules[xr][3];

                    // not in original code -- added for dm hebrew, never encountered used in dm latin
                    // occurs only when a vowel is in the branching case (e.g., the VAV in hebrew)
                    } else if (xr >= 0 && xnewrules[xr][3] == "999") {
                      // branching case, is a vowel, so reset previous one to blank
                      lastdm[ii] = "";

                    } else {
                      if (xr < 0 && newrules[i][3] != "999" && newrules[i][3] != lastdm[ii]) {
                        // non-branching case, not a vowel and different code from prevous case
                        lastdm[ii] = newrules[i][3];
                        dm2[ii] += newrules[i][3];
                      } else if (newrules[i][3] == 999) {
                        // non-branching case, is a vowel, so reset previous one to blank
                        lastdm[ii] = "";
                      }
                    }
                  }
                }
              }
            }

            break; // stop looping through rules
          } // end of match found

        } // end of looping through the rules
      } // end of while (MyStr.length) > 0)
      dm = ""
      for (ii=0; ii<dim_dm2; ii++) {
        dm2[ii] = (dm2[ii] + "000000").substr(0, 6);
        if (ii == 0 && dm.indexOf(dm2[ii]) == -1 && dm3.indexOf(dm2[ii]) == -1) {
          dm = dm2[ii];
        } else {
          if (dm.indexOf(dm2[ii]) == -1 && dm3.indexOf(dm2[ii]) == -1) {
            if (dm.length > 0) {
              dm = dm + SEPARATOR + dm2[ii];
            } else {
              dm = dm2[ii];
            }
          }
        }
      }

      if (dm3.length > 0 && dm3.indexOf(dm) == -1) {
        dm3 = dm3 + SEPARATOR + dm;
      } else {
        if (dm.length > 0) {
          dm3 = dm;
        }
      }

    }

  } // end of while

  dm = dm3;
  return dm;
}

function FixVav(rawtext) {
  // force single VAV to be a vowel (i.e., replace with an AYIN) in the following cases:
  //    preceded by BAIS or PAY
  //    followed by MEM or NUN
  // force double VAV to be a consonant (i.e., replace with a BAIS)

  // this also fixes double YUD as well, forcing it to always be a vowel and never "YI"

  text = "";
  for (var i=0; i<rawtext.length; i++) {
    var ch = rawtext.charAt(i);
    var prevChar = (i==0) ? "" : rawtext.charAt(i-1);
    var nextChar = (i==rawtext.length-1) ? "" : rawtext.charAt(i+1);
    var nextNextChar = (i==rawtext.length-2) ? "" : rawtext.charAt(i+2);

    if (ch == VAV) {
      if (nextChar == VAV) { // double VAV
        ch = BAIS;
        i++;
      } else if (nextChar == MEM || nextChar == MEM2 || nextChar == NUN || nextChar == NUN2) {
        // single VAV followed by MEM or NUN
        ch = AYIN;
      } else if (prevChar == BAIS || prevChar == PAY) {
        // preceded by a BAIS or PAY
        ch = AYIN;
      }
    } else if (ch == YUD && nextChar == YUD) {
      if (i == rawtext.length-3 && nextNextChar == HAY) {
        // leave YUD YUD HAY at end of name in tact and let the table take care of it (generate a 1)
        ch = YUD + YUD + HAY;
        i += 2;
      } else if (i <= rawtext.length-3 && nextNextChar == AYIN) {
        // leave YUD YUD AYIN in tact and let the table take care of it (generate a 1)
        ch = YUD + YUD + AYIN;
        i += 2;
      } else {
        // treat all other double YUDs as a vowel instead of Yi
        ch = AYIN;
        i++;
      }
    }
    text += ch;
  }
  return text;
}

function SoundexWithoutDuplicateConsonantRule(rawtext, separator) {

  // Suspend the dm duplicate-consonant rule
  // Do so by forcing a vowel in between them, which is probably the case in hebrew
  // But there are times when we don't want to suspend it, so let's do both
  // Don't use ALEF for the vowel because of the ALEF VAV rule in the branching case

  var words = rawtext.split(" ");

  var combinedSoundex = "";
  for (y=0; y<words.length; y++) {
    text = words[y];

    // first create an array of all alternates for this word, with and without intervening vowels

    var text2 = "";
    var textArray = [""];
    for (var i=0; i<text.length; i++) {
      var ch = text.charAt(i);
      if (ch < ALEF || ch > TAF) {
        continue;
      }
      for (x=0; x<textArray.length; x++) {
        textArray[x] += ch;
      }
      if (i!=(text.length-1) && !IsVowel(text.charAt(i)) && !IsVowel(text.charAt(i+1))) {
        if (text.charAt(i) == VAV && text.charAt(i+1) == VAV) {
          continue; // don't insert a vowel between two consecutive VAVs
        }
        // might want to be selective here, like doing it only for certain letter combinations
        var textArrayUpperHalf = textArray.length;
        for (x=0; x<textArrayUpperHalf; x++) {
          textArray[textArrayUpperHalf+x] = textArray[x] + AYIN; // don't use alef -- see above
        }
      }
    }

    // unravel the array into a single string of alternates

    for (var x=0; x<textArray.length; x++) {
      if (text2 != "") {
        text2 += " ";
      }
      text2 += textArray[x];
    }

    // generate the soundex of each alternate in the string

    var rawSoundex = soundex(text2);

    // remove duplicated soundex codes

    var wordSoundex = "";
    var soundexArray = rawSoundex.split(" ");
    soundexArray.sort();
    for (x=0; x<soundexArray.length; x++) {
      if (x == 0) {
        wordSoundex = soundexArray[x];
      } else {
        if (soundexArray[x] != soundexArray[x-1]) {
          wordSoundex += " " + soundexArray[x];
        }
      }
    }

    // combine with the soundex of any preceding words

    if (combinedSoundex != "") {
      combinedSoundex += separator;
    }
    combinedSoundex += wordSoundex;
  }

  // return the result

  return combinedSoundex;
}

function IsVowel(value) {
  return (value==ALEF || value == AYIN || value == YUD);
}

//var text = process.argv[2];
//console.log(SoundexWithoutDuplicateConsonantRule(FixVav(text), " "));

var http = require('http');
const PORT = process.argv[2] ? process.argv[2] : 8765;

function handleRequest(request, response){
  var name = require('url').parse(request.url, true).query.n,
      dmCode = SoundexWithoutDuplicateConsonantRule(FixVav(name), " ");
  console.log(name, '=>', dmCode);
  response.end(dmCode + '\n');
}

var server = http.createServer(handleRequest);

server.listen(PORT, function(){
  console.log("DMS server listening on: http://localhost:%s. Send requests in 'n' query parameter.", PORT);
});

