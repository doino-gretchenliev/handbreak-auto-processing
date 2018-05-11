Handbreak auto processing tool
==============================
Watch for new media files and automatically process them with Handbreak or other transcoding tool

---   
### Requirements

* Python 2.7
* Install all dependencies with the following command:
`pip install -r requirements.txt`

### How To Use

The tool exopses two enviorment variables for usage in the provided command or script:
* `INPUT_FILE`: the current file for processing
* `OUTPUT_FILE`: the name of the file after processing
Example:
`INPUT_FILE=~/Movies/movie-name.mp4`
`OUTPUT_FILE=~/Movies/movie-name_transcoded.mp4`

#### Basic usage

```bash
handbreak-auto-processing.py \
-w ~/Movies \
-w ~/Shows \
-w ~/Anime \
-c 'HandBrakeCLI --preset x265-10bit --input $INPUT_FILE --output $OUTPUT_FILE'
```

#### Pipeline usage(Handbreak & Filebot)

```bash
handbreak-auto-processing.py \
-w ~/Movies \
-c 'HandBrakeCLI --preset x265-10bit --input $INPUT_FILE --output $OUTPUT_FILE &&
filebot -rename $OUTPUT_FILE --db anidb -non-strict'
```

#### Log files

The main log file of the tool is `handbreak-auto-processing.log`. 
For each transcoding task the tool creates a file in the destination directory named after the processing file e.g.:
processing file: `~/Movies/movie-name.mp4`
processing log file: `~/Movies/movie-name_transcoding.log`

#### Documentation
  
| Option String | Required | Choices | Default| Summary |  
|---------------|----------|---------|--------|----------------|  
| ['-h', '--help'] | False | None | N/A | show this help message and exit | 
| ['-l', '--list-processing-queue'] | False | N/A | False | Lists processing queue and exits | 
| ['-n', '--retry-media-file'] | False | N/A | False | Change media file state from [failed] to [waiting] | 
| ['-a', '--retry-all-media-files'] | False | N/A | False | Change all media file states from [failed] to [waiting] | 
| ['-p', '--initial-processing'] | False | N/A | False | Find and process all files in listed in watch directories(excludes failed media files) | 
| ['-r', '--reprocess'] | False | N/A | False | Whether to reprocess files already in processing queue with state [processed] | 
| ['-w', '--watch-directory'] | False | N/A | None | Directory to watch for new media files | 
| ['-q', '--queue-directory'] | False | N/A | run user home directory | Directory to store processing queue(NOTE: if you're running the tool on more than one machines both running instances of this script should have access to processing queue) | 
| ['-i', '--include-pattern'] | False | N/A | ['*.mp4', '*.mpg', '*.mov', '*.mkv', '*.avi'] | Include for processing files matching include patterns | 
| ['-e', '--exclude-pattern'] | False | N/A | None | Exclude for processing files matching include patterns | 
| ['-s', '--case-sensitive'] | False | N/A | depends on the filesystem | Whether pattern matching should be case sensitive | 
| ['-v', '--verbose'] | False | N/A | False | Enable verbose log output | 
| ['-m', '--max-log-size'] | False | N/A | 100 | Max log size in MB; set to 0 to disable log file rotating | 
| ['-k', '--max-log-file-to-keep'] | False | N/A | 1 | Max number of log files to keep | 
| ['-c', '--handbreak-command'] | False | N/A | None | Handbreak command to execute | 
| ['-t', '--handbreak-timeout'] | False | N/A | 15 | Timeout of Handbreak command(hours) | 
| ['-f', '--file-extension'] | False | N/A | mp4 | Output file extension | 
| ['-d', '--delete'] | False | N/A | False | Delete original file |   
| ['-z', '--silent-period'] | False | N/A | None | A silent period(the media processing command will be suspended) defined as so: [18:45:20:45]. You can provide multiple periods |
| ['-x', '--rest-api'] | False | N/A | False | Enable REST API mapped on port 6000 |
