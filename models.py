"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    num_of_wons = ndb.IntegerProperty(required=True, default=0)
    games_played = ndb.StringProperty(repeated=True)


class Game(ndb.Model):
    """Game object"""
    target = ndb.IntegerProperty(required=True)
    attempts_allowed = ndb.IntegerProperty(required=True)
    attempts_remaining = ndb.IntegerProperty(required=True, default=5)
    game_canceled = ndb.BooleanProperty(required=True, default=False)
    game_over = ndb.BooleanProperty(required=True, default=False)
    num_of_wons = ndb.IntegerProperty(required=True, default=0)
    won = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    

    @classmethod
    def new_game(cls, user, attempts):
        """Creates and returns a new game"""
        game = Game(user=user,
                    num_of_wons=0,
                    target=random.choice(range(1, 32)),
                    attempts_allowed=attempts,
                    attempts_remaining=attempts,
                    game_over=False,
                    won=False
                    )
        game.put()
        return game

    def to_form(self, message):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.attempts_remaining = self.attempts_remaining
        form.num_of_wons = self.num_of_wons
        form.game_over = self.game_over
        form.won = self.won
        form.message = message
        return form

    def end_game(self, won, num_of_wons):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        self.put()
        # Add the game to the score 'board'
        score = Score(user=self.user, date=date.today(), won=won,
                      guesses=self.attempts_allowed - self.attempts_remaining, num_of_wons=num_of_wons)
        score.put()

    def canceled_game(self):
        self.game_canceled = True
        self.put()


class Score(ndb.Model):
    """Score object"""
    user = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True, default=False)
    guesses = ndb.IntegerProperty(required=True)
    num_of_wons = ndb.IntegerProperty(required=True, default=0)

    def to_form(self):
        return ScoreForm(user_name=self.user.get().name, won=self.won,
                         date=str(self.date), guesses=self.guesses, num_of_wons=self.num_of_wons)


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user_name = messages.StringField(5, required=True)
    num_of_wons = messages.IntegerField(6, required=True)
    won = messages.BooleanField(8, required=True)


class GameForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)
    attempts = messages.IntegerField(2, default=5)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    pick_a_date = messages.IntegerField(1, required=True)
    user_name = messages.StringField(2, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    guesses = messages.IntegerField(4, required=True)
    num_of_wons = messages.IntegerField(5, default=0)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)

class LimitResults(messages.Message):
    """StringMessage-- outbound (single) string message"""
    limit = messages.IntegerField(1)
