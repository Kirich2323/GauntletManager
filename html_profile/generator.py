import math

def gen_award_div(awards):
    return "\n".join(f'<img src="{a}" class="award">' for a in awards)

def gen_sniped_most_html_string(sniped):
    return "\n".join([ f'<div class="sniped-wrapper"><div class="sniped-name">{x[0]}</div>\n<div class="sniped-value">{x[1]}</div></div>' for x in sniped])

def to_flt_or_none(val):
    return f'{val:.2f}' if val else 'None'

def generate_profile_html(user, stats, avatar_url):
    user_awards = gen_award_div(stats.awards)
    sniped_most_html_string = gen_sniped_most_html_string(stats.most_sniped)
    watched_most_html_string = gen_sniped_most_html_string(stats.most_watched)
    karma_urls = [
        'https://i.imgur.com/wscUx1m.png',
        'https://i.imgur.com/wscUx1m.png', # <-- two black hearts
        'https://i.imgur.com/oiypoFr.png',
        'https://i.imgur.com/4MOnqxX.png',
        'https://i.imgur.com/UJ8yOJ8.png',
        'https://i.imgur.com/YoGSX3q.png',
        'https://i.imgur.com/DeKg5P5.png',
        'https://i.imgur.com/byY9AfE.png',
        'https://i.imgur.com/XW4kc66.png',
        'https://i.imgur.com/3pPNCGV.png',
    ]
    url_idx = math.floor(stats.karma / 100)
    url_idx = min(url_idx, len(karma_urls))
    karma_url=karma_urls[url_idx]
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css'>
    <link rel="stylesheet" href="styles.css">
</head>

<body>
    <div class="center">
        <div class="card">
            <div class="line"></div>
            <div class="additional" style="background-color: {'#'+user.color[1:]};">
                <div class="user-card">
                    <div class="user-name center">{user.name}</div>
                    <div class="awards center">
                        {user_awards}
                    </div>

                    <img src={avatar_url} width="110" height="110" class="avatar center" alt="">
                </div>
            </div>
            <div class="general">
                <div class="more-info">
                    <div class="stats">
                        <div class="karma">
                            <div class="title">Karma</div>
                            <i class="fa fa-heart" aria-hidden="true"></i>
                            <div class="value">{stats.karma:.2f}</div>
                        </div>

                        <div class="completed">
                            <div class="title">Completed</div>
                            <i class="fa fa-trophy"></i>
                            <div class="value">{stats.num_completed}</div>
                        </div>

                        <div class="avg-score">
                            <div class="title">Avg. Score</div>
                            <i class="fa fa-wheelchair-alt"></i>
                            <div class="value">{to_flt_or_none(stats.avg_rate)}</div>
                        </div>

                        <div class="your-avg-score">
                            <div class="title">Title Score</div>
                            <i class="fa fa-list" aria-hidden="true"></i>
                            <div class="value">{to_flt_or_none(stats.avg_title_score)}</div>
                        </div>

                        <div class="sniped">
                            <div class="title">Sniped</div>
                             {sniped_most_html_string}                           
                        </div>

                        <div class="got-sniped">
                            <div class="title">Watched</div>
                             {watched_most_html_string}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''