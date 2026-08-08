THE FIRST COMMANDMENT: THE GOLDEN RULE:
The AI_Music_Blender GitHub repository, hereinafter known as "AI_Music_Blender",
descends from the Infinite Jukebox lineage (Echo Nest Labs, The Eternal Jukebox, EternalBox),
and the original Infinite Jukebox functionality must keep working, unmodified in behavior,
at every stage of this project.

All new features are additive - new modules, new entry points, new modes -
never edits that change what the classic mode does.

The guiding story and plan are recorded in:
/home/ccaitwo/AI_Music_Blender/docs/AI_Music_Blender_Vision_Document.txt

THE SECOND COMMANDMENT: SELF-HOSTING:
Every ancestor of this project died because it depended on someone else's server or
Application Programming Interface (API): first Echo Nest, then Spotify, then an abandoned backend.

AI_Music_Blender therefore performs ALL audio analysis locally, on the user's own machine,
with a self-hosted Machine Learning (ML) pipeline (librosa and friends).

No feature may ever depend on an external analysis API.

Nothing to deprecate.

Nothing to die.

THE THIRD COMMANDMENT: THE DSPARCD FILESET:
The seven (7) step waterfall workflow documents are inspired by the specification file:
/home/ccaitwo/AI_Music_Blender/docs/DSPARCD_EXPLAINED.txt

The versioned files are created and named:
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_1_definition_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_2_specification_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_3_pseudocode_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_4_architecture_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_5_refinement_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_6_completion_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/ai_music_blender_7_demonstration_v1.txt

These seven (7) files will be known as "The DSPARCD Fileset".

(Note: cousin repositories carry six SPARCD documents; AI_Music_Blender is the family's first
DSPARCD project, so it carries seven, with Definition at the front where it belongs.)

THE FOURTH COMMANDMENT: ENGLISH READABLE CODE:
Pseudocode will be inspired and influenced by English Readable Code (ERC) as defined in the
specification file:
/home/ccaitwo/AI_Music_Blender/docs/ENGLISH_READABLE_CODE_MANUSCRIPT.txt

Concretely: every line of code in every source file carries one plain-English comment
immediately above it, indented to match, per the ERC rule.

THE FIFTH COMMANDMENT: THE ARCHIVE:
A directory /home/ccaitwo/AI_Music_Blender/docs/archive/ shall exist.

When new versions of files are written, the older, superseded files will be moved to the
/archive/ folder for storage (using git mv, in the same change), so that only the latest
version of any versioned document lives outside /archive/.

THE SIXTH COMMANDMENT: MIRRORED DOCUMENTS:
Any and all code changes to AI_Music_Blender will be accompanied by mirrored changes to
"The DSPARCD Fileset", with version numbers incremented, and older versions archived per
the Fifth Commandment.

THE SEVENTH COMMANDMENT: THE TUTORIALS:
Two tutorials live in /docs/ and are versioned under the Fifth Commandment:
/home/ccaitwo/AI_Music_Blender/docs/User_Tutorial_v1.txt
/home/ccaitwo/AI_Music_Blender/docs/Developer_Tutorial_v1.txt

The User Tutorial teaches a beginner, learner, layperson, newcomer, or novice how to USE
AI_Music_Blender in all three ways it runs (command line, localhost web page, Ubuntu
Graphical User Interface (GUI) app).

The Developer Tutorial teaches a newcomer developer how the system WORKS inside, module by
module, and how to extend it without breaking the Golden Rule.

Both tutorials are updated, with versions incremented, as code changes are applied,
so each always describes the AI_Music_Blender that exists.

THE EIGHTH COMMANDMENT: THE README:
/home/ccaitwo/AI_Music_Blender/README.md will be kept up to date as the project develops,
in the same style, look, and feel as the README.md files of the cousin repositories
(causalontology, PrologAI, Mentova, konnectome).

(Initially, a placeholder banner image; the USER will replace it later.)

THE NINTH COMMANDMENT: LEGALITY AND LOCALITY:
AI_Music_Blender runs on the user's own audio files and local downloads, renders locally,
and hosts and distributes NOTHING.

No accounts, no API keys, no telemetry, no uploads.

Keep it that way.

THE TENTH COMMANDMENT: ONE ENGINE, THREE FACES:
The command line interface, the localhost web page, and the Ubuntu GUI app are all thin
faces over ONE shared engine (the ai_music_blender Python package).

A capability added to the engine is added once; a face merely exposes it.

Future faces (Windows, Mac, iPhone, Android) will follow the same rule.

THE ELEVENTH COMMANDMENT: WHOLE WORDS:
AI_Music_Blender is a "Whole-Word System", for clarity, readability, and understandability,
not an abbreviation system or single-letter system.

Module, function, and variable names are whole English words, snake_case.

External standard names (librosa, ffmpeg, JSON, MFCC as a defined term) keep their real names.

THE TWELFTH COMMANDMENT: THE BUILD LOG:
Activities of the AI_Music_Blender build are logged to the versioned document:
/home/ccaitwo/AI_Music_Blender/docs/BUILDING_AI_MUSIC_BLENDER_v1.txt

The log is append-only and grows with the build, voiced with dual purpose: as a scientific
paper and as a good story.

END OF CONSTITUTION.
