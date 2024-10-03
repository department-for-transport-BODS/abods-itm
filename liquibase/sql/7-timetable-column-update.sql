--changeset abodsuser:7

-- Adding new columns for journeys
ALTER TABLE  public."Timetable"
ADD COLUMN off_set integer NULL,
ADD COLUMN journey_pattern integer[] NULL;