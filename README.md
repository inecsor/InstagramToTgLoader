### Setup

To make this code work you need to fill Credentials.py with actual data and install requirements from requirements.txt

### Request arguments

The `--username` and `--password` arguments are required to generate a new cookie file or when an existing cookie file has expired. You can omit these two arguments if there is a working login cookie file available already.

`--download` — User(s) to download. Multiple users must be seperated by a space.

`--taken-at` — PyInstaStories will save files with a datetime format: `2019-01-07_22-51-43.jpg`

`--no-thumbs` — PyInstaStories will skip downloadable video story thumbnail images.

`--output` — PyInstaStories will create output folder automatically if not provided.

### Example

Download stories of 1 user. Save files with a datetime format and skip downloading of video thumbnail images.  
`python3 StoryLoader.py -d lnecsor --taken-at --no-thumbs`
