from nltk.corpus import stopwords
import requests
from newspaper import Article
from flask import Flask, render_template, url_for, request, redirect
from google.cloud import language_v1
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
import redis
import os
import json

redis_host = os.environ['REDIS_HOST']
redis_port = int(os.environ['REDIS_PORT'])


redis_client = redis.Redis(host=redis_host, port=redis_port)

# print('From Redis', redis_client.get('fname'))

nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')

app = Flask(__name__)


sections = """arts, automobiles, books, business, fashion, food, health, insider, magazine, movies, New York, opinion, politics, realestate, science, sports, sundayreview, technology, theater, t-magazine, travel, upshot, us, world"""

sections = sections.split(', ')

sections = [section.title() for section in sections]


def text_process(text):
    sentences = sent_tokenize(text)
    words = word_tokenize(text)

    stop_words = set(stopwords.words("english"))

    filtered_words = []

    for word in words:
        if word not in stop_words:
            filtered_words.append(word)

    total_sent_length = 0
    for sent in sentences:
        total_sent_length += len(word_tokenize(sent))

    total_word_length = 0

    for word in filtered_words:
        total_word_length += len(word)

    avg_word_length = total_word_length/len(filtered_words)
    avg_sent_length = total_sent_length/len(sentences)
    avg_read_time = f"{round(len(words)/265,2)} min(s)"

    result = {

        "Avg. Word Length": round(avg_word_length, 2),
        "Avg. Sent Length": round(avg_sent_length, 2),
        "Avg. Read Time": avg_read_time
    }

    print(result)

    return result


def sample_analyze_sentiment(text_content):
    """
    Analyzing Sentiment in a String

    Args:
      text_content The text content to analyze
    """

    client = language_v1.LanguageServiceClient()

    type_ = language_v1.Document.Type.PLAIN_TEXT

    language = "en"
    document = {"content": text_content, "type_": type_, "language": language}

    encoding_type = language_v1.EncodingType.UTF8

    response = client.analyze_sentiment(
        request={'document': document, 'encoding_type': encoding_type})

    print(u"Document sentiment score: {}".format(
        response.document_sentiment.score))
    print(
        u"Document sentiment magnitude: {}".format(
            response.document_sentiment.magnitude
        )
    )

    norm_score = ((response.document_sentiment.score+1)/2)*5

    return norm_score


@app.route("/")
@app.route("/home")
def home():

    section = request.args.get('section')
    section = section if section else 'world'

    print(f'User watching section- {section}')

    api_key = 'D2xAlAGIKwxEUL7AEhiAG4mXLRysRUG8'
    url = f"https://api.nytimes.com/svc/topstories/v2/{section}.json?api-key={api_key}"

    response = requests.get(url=url)

    if response.ok:
        data = response.json()
        meta_data = {
            'num_results': data['num_results']
        }

        articles = data['results']

        return render_template('home.html', articles=articles, sections=sections)
    else:
        return render_template('home.html', sections=sections)


@app.route("/about")
def about():
    return render_template('about.html', title='About', sections=sections)


@app.route("/most_popular")
def most_popular():
    return render_template('most_popular.html', title='Most-popular', sections=sections)


@app.route("/movie_reviews")
def movie_reviews():
    return render_template('movie_reviews.html', title='movie_reviews', sections=sections)


@app.route("/nyt_archives")
def nyt_archives():
    return render_template('nyt_archives.html', title='nyt_archives', sections=sections)


@app.route("/nyt_article")
def nyt_article():

    article_url = request.args.get('url')
    article_title = request.args.get('article_title')

    print('\n\nArticle URL', article_url)

    if article_url:
        if redis_client.exists(article_url):
            cached_data = redis_client.get(article_url).decode('utf-8')
            cached_data = json.loads(cached_data)

            return render_template('article.html', title='Article Insights',
                                   article_title=article_title,
                                   sections=sections,

                                   article_insights=cached_data)

        article_data = Article(url=article_url)

        article_data.download()
        article_data.parse()
        article_data.nlp()

        authors = article_data.authors
        summary = article_data.summary
        publish_date = article_data.publish_date
        keywords = ', '.join(article_data.keywords)
        article_text = article_data.text

        avg_metrics = text_process(article_text)

        sentiment_score = round(sample_analyze_sentiment(article_text), 2)

        sentiment_score = f"{sentiment_score}/5"
        print('positivity', sentiment_score)

        article_insights = {
            'summary': summary,
            'keywords': keywords,
            'url': article_url,
            'article_text': article_text,
            'avg_metrics': avg_metrics,
            'positivity': sentiment_score

        }

        redis_client.set(article_url, json.dumps(article_insights))

        return render_template('article.html', title='Article Insights',
                               article_title=article_title,
                               sections=sections,

                               article_insights=article_insights)

    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
