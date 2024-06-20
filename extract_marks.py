#!/usr/bin/env python3
"""FAIS Minus --- a script for handling final marks exported from Wattle Gradebook

OVERVIEW:

This script helps process the final mark output from Gradebook, including:

- generating stats per cohort 
- recording and updating special grades (e.g., DA/RP/WD)
- exporting CSV files that are _actually_ SAS-ready.

N.B.: This script has a setting that replaces a grade of 0 by NCN (on the basis that a student did not attempt any task). By default it is turned off (false).

REQUIREMENTS:

- pandas
- pyyaml

USAGE:

1. export the CSV marks "for_SAS" from Gradebook and place them in the same directory as this script.
2. create a grade_config.yml file to store information not available in the spreadsheet (see below)
3. run the script: `python3 examiner_meeting_data.py`

GRADE CONFIG FILE:

Specifically, the grade_config file defines:

For each course code COMPXXXX in your for_SAS output:

- type of course (UGRD/PGRD)
- term number (each ANU semester has a specific 4-digit number, it's predictable, you can find it on Programs & Courses or use this image <https://pasteboard.co/CUmJzNza7PV7.png>
- subject code (4-letter start of the course code, usually "COMP" for SoCo)
- catalogue number (4-digit end of the course code, e.g. 1100 for COMP1100)
- class number (4-digit code specific to each instance of a specific course, look in Programs & Courses to find this)

And most importantly:

- special grades that are not predictable from your for_SAS gradebook output:
    - DA (deferred assessment)
    - RP (result pending usually related to academic integrity)
    - WD/WN (withdrawn without/with failure: info sent by academic services before examiners' meeting)
    - PS/N (_after_ examiners' meetings you can use this sytem to record which students have passed/failed supplementary assessments)

The grade config file should have the format:

COMPxxxx:
  type: UGRD
  term: 1234
  subject: COMP
  catalogue: xxxx
  class: 1234
  grades:
    u1234567: XX # where XX is the special grade to apply to specific students.

COMPyyyy:
  type: PGRD
  term: 1234
  subject: COMP
  catalogue: yyyy
  class: 5678
  grades:
    u1234567: XX # where XX is the special grade to apply to specific students.

This script is a fully-subscribed member of the "works on my machine" certification program. If it's broken and you update it, let us know for others to benefit!
"""
import pandas as pd
import yaml
import os

# setting to convert grades of 0 to NCN (on the basis that this is only possible if a student does not attempt any task).
set_0_ncn = False
# this may not be appropriate in all situations.

# load marks
possible_sas_exports = [f for f in os.listdir(".") if "for_SAS" in f ]
print("Loading Files...")
print(f"Options are: {possible_sas_exports}")
print(f"Opening: {possible_sas_exports[0]}")
all_marks = pd.read_csv(possible_sas_exports[0])
all_marks["course_code"] = all_marks["Enrol Reason"].apply(lambda x: x[0:8])
all_marks["uid"] = all_marks["Student Number"].apply(lambda x: f'u{x}')
all_marks = all_marks.set_index("uid")
all_marks["Student Number"] = all_marks["Student Number"].astype(int)
courses = list(all_marks.course_code.unique())

# load config
with open("grade_config.yml", "r") as stream:
    try:
        config = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

def generate_grade(mark):
    if mark == 0:
        if set_0_ncn:
            return 'NCN'
        else:
            return 'N'
    if mark <= 44:
        return "N"
    if mark <= 49:
        return "PX"
    if mark <= 59:
        return "P"
    if mark <= 69:
        return "CR"
    if mark <= 79:
        return "D"
    return "HD"


## add grades
mark_column = all_marks.columns[1]
# print(f"mark column is: {mark_column}")
all_marks["grade"] = all_marks[mark_column].apply(generate_grade)

## add special grades
for c in courses:
    special_grades = config[c]['grades']
    if special_grades is not None:
        for uid in special_grades:
            all_marks.at[uid,'grade'] = special_grades[uid]

## update student number to be int
all_marks["Student Number"] = all_marks["Student Number"].astype(int)
all_marks[mark_column] = all_marks[mark_column].astype(int)
# all_marks = all_marks.sort_index()

def print_stats(name, df):
    with pd.option_context("float_format", "{:.2f}".format):
        print(f'## {name}\n')
        print(f'Enrolment: {len(df.index)}\n')
        print("Mark Stats")
        print(df[mark_column].describe())
        print('\n')
        print_value_counts(df)
        print('\n')
        
def print_value_counts(df):
    counts = df.grade.value_counts()
    total = len(df.index)
    print("Grade Value Counts")
    for grade in ['HD', 'D','CR','P','PX','N','NCN','DA','RP','KU','WD','WN']:
        try:
            print(f"{grade}: {counts[grade]} ({(counts[grade] * 100/total):.2f}%)")
        except:
            continue


## remove WD and WN students
all_marks = all_marks[all_marks['grade'] != "WD"]
all_marks = all_marks[all_marks['grade'] != "WN"]

## print the stats
print("\nPrinting stats...")

with pd.option_context("float_format", "{:.2f}".format):
    print_stats("All Cohorts", all_marks)
    for c in courses:
        print_stats(c, all_marks[all_marks.course_code == c])

print("\nPrinting PXs...")

if len(all_marks[all_marks['grade'] == "PX"]) > 0:
    print(all_marks[all_marks['grade'] == "PX"])
    print(all_marks[all_marks['grade'] == 'PX']["Student Number"].apply(lambda x : f'u{x}@anu.edu.au'))
else: 
    print("\nNo PXs to print. (lucky!)")

print("\nSaving SAS-ready CSVs...")

## SAS Export
interim_codes = ['DA', 'PX','RP', 'KU', 'NCN']

## copy interim grades to mark column
for uid in all_marks.index:
    g = all_marks.at[uid,'grade']
    if g in interim_codes:
        all_marks.at[uid,mark_column] = g

## split into per-course CSV files with proper columns and names and interim codes in mark column
for c in courses:
    course_marks = all_marks[all_marks.course_code == c]
    csv_cols = ["Student Number", mark_column, "grade", "First name", "Last name", "course_code"]
    sas_header = []
    header = ['uid', 'mark', 'grade', 'firstname', 'surname', 'course']
    # header = [config[c]["type"], config[c]["term"], config[c]["class"], 'firstname', 'lastname', 'course']
    sas_filename = f'{config[c]["term"]}-{config[c]["subject"]}-{config[c]["catalogue"]}-{config[c]["class"]}.csv'
    course_marks[csv_cols].to_csv(sas_filename, header=header, index=False)
    print(f"Saved: {sas_filename}")
