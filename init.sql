CREATE TABLE guild (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	discord_id INTEGER NOT NULL UNIQUE,
	current_challenge_id INTEGER DEFAULT NULL,
	spreadsheet_key TEXT DEFAULT NULL,

	FOREIGN KEY (current_challenge_id) REFERENCES challenge (id) ON DELETE SET NULL
);

CREATE TABLE user (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	discord_id INTEGER NOT NULL UNIQUE,
	color VARCHAR(7),
	name TEXT NOT NULL,

	CHECK(color LIKE '#%')
);

CREATE TABLE challenge (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	guild_id INTEGER NOT NULL,
	name TEXT NOT NULL,
	start_time TIMESTAMP NOT NULL,
	finish_time TIMESTAMP DEFAULT NULL,
	award_url TEXT DEFAULT NULL,

	FOREIGN KEY (guild_id) REFERENCES guild (id)
);

CREATE TABLE participant (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	challenge_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	failed_round_id INTEGER DEFAULT NULL,
	progress_current INTEGER DEFAULT NULL,
	progress_total INTEGER DEFAULT NULL,

	UNIQUE (challenge_id, user_id),
	FOREIGN KEY (challenge_id) REFERENCES challenge (id),
	FOREIGN KEY (user_id) REFERENCES user (id),
	FOREIGN KEY (failed_round_id) REFERENCES round (id)
);

CREATE TABLE pool (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	challenge_id INTEGER NOT NULL,
	name TEXT NOT NULL,

	UNIQUE(challenge_id, name),
	FOREIGN KEY (challenge_id) REFERENCES challenge (id)
);

CREATE TABLE title (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	pool_id INTEGER NOT NULL,
	participant_id INTEGER NOT NULL,
	name TEXT NOT NULL,
	url TEXT,
	is_used BOOLEAN NOT NULL DEFAULT 0,

	FOREIGN KEY (pool_id) REFERENCES pool (id),
	FOREIGN KEY (participant_id) REFERENCES participant (id) ON DELETE CASCADE
);

CREATE TABLE round (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	num INTEGER NOT NULL,
	challenge_id INTEGER NOT NULL,
	start_time TIMESTAMP NOT NULL,
	finish_time TIMESTAMP NOT NULL,
	is_finished BOOLEAN NOT NULL DEFAULT 0,

	UNIQUE (challenge_id, num),
	FOREIGN KEY (challenge_id) REFERENCES challenge (id)
);

CREATE TABLE roll (
	round_id INTEGER NOT NULL,
	participant_id INTEGER NOT NULL,
	title_id INTEGER NOT NULL,
	score REAL DEFAULT NULL,

	UNIQUE (round_id, participant_id),
	FOREIGN KEY (round_id) REFERENCES round (id),
	FOREIGN KEY (participant_id) REFERENCES participant (id) ON DELETE CASCADE,
	FOREIGN KEY (title_id) REFERENCES title (id) ON DELETE CASCADE
);

CREATE TABLE award (
	participant_id INTEGER NOT NULL,
	"url" TEXT DEFAULT NULL,
	"time" TIMESTAMP NOT NULL,
	FOREIGN KEY (participant_id) REFERENCES participant (id)
);

CREATE TABLE karma_history (
	user_id INTEGER NOT NULL,
	karma INTEGER NOT NULL,
	"time" TIMESTAMP NOT NULL,

	FOREIGN KEY (user_id) REFERENCES user (id)
);