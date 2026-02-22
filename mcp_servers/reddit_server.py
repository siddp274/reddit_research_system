from enum import Enum
import json
import redditwarp.SYNC
# from fastmcp.server.depdendencies import get_http_headers
from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, Field


class PostType(str, Enum):
    LINK = "link"
    TEXT = "text"
    GALLERY = "gallery"
    UNKNOWN = "unknown"



class SubredditInfo(BaseModel):
    name: str
    subscriber_count: int
    description: str | None


class Post(BaseModel):
    id: str
    title: str
    author: str
    score: int
    subreddit: str
    url: str
    created_at: str
    comment_count: int
    post_type: PostType
    content: str | None


class Comment(BaseModel):
    id: str
    author: str
    body: str
    score: int
    replies: list['Comment'] = Field(default_factory=list)


class Moderator(BaseModel):
    name: str


class PostDetail(BaseModel):
    post: Post
    comments: list[Comment]


class RedditServer:
    def __init__(self):
        self.client = redditwarp.SYNC.Client()

    def _get_post_type(self, submission) -> PostType:
        """Helper method to determine post type"""
        if isinstance(submission, redditwarp.models.submission_SYNC.LinkPost):
            return PostType.LINK
        elif isinstance(submission, redditwarp.models.submission_SYNC.TextPost):
            return PostType.TEXT
        elif isinstance(submission, redditwarp.models.submission_SYNC.GalleryPost):
            return PostType.GALLERY
        return PostType.UNKNOWN

    # The type can actually be determined by submission.post_hint
    # - self for text
    # - image for image
    # - hosted:video for video
    def _get_post_content(self, submission) -> str | None:
        """Helper method to extract post content based on type"""
        if isinstance(submission, redditwarp.models.submission_SYNC.LinkPost):
            return submission.permalink
        elif isinstance(submission, redditwarp.models.submission_SYNC.TextPost):
            return submission.body
        elif isinstance(submission, redditwarp.models.submission_SYNC.GalleryPost):
            return str(submission.gallery_link)
        return None

    def _build_post(self, submission) -> Post:
        """Helper method to build Post object from submission"""
        return Post(
            id=submission.id36,
            title=submission.title,
            author=submission.author_display_name or '[deleted]',
            score=submission.score,
            subreddit=submission.subreddit.name,
            url=submission.permalink,
            created_at=submission.created_at.astimezone().isoformat(),
            comment_count=submission.comment_count,
            post_type=self._get_post_type(submission),
            content=self._get_post_content(submission)
        )

    def get_frontpage_posts(self, limit: int = 10) -> list[Post]:
        """Get hot posts from Reddit frontpage"""
        posts = []
        for subm in self.client.p.front.pull.hot(limit):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_info(self, subreddit_name: str) -> SubredditInfo:
        """Get information about a subreddit"""
        subr = self.client.p.subreddit.fetch_by_name(subreddit_name)
        return SubredditInfo(
            name=subr.name,
            subscriber_count=subr.subscriber_count,
            description=subr.public_description
        )

    def _build_comment_tree(self, node, depth: int = 3) -> Comment | None:
        """Helper method to recursively build comment tree"""
        if depth <= 0 or not node:
            return None

        comment = node.value
        replies = []
        for child in node.children:
            child_comment = self._build_comment_tree(child, depth - 1)
            if child_comment:
                replies.append(child_comment)

        return Comment(
            id=comment.id36,
            author=comment.author_display_name or '[deleted]',
            body=comment.body,
            score=comment.score,
            replies=replies
        )

    def get_subreddit_hot_posts(self, subreddit_name: str, limit: int = 10) -> list[Post]:
        """Get hot posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.hot(subreddit_name, limit):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_new_posts(self, subreddit_name: str, limit: int = 10) -> list[Post]:
        """Get new posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.new(subreddit_name, limit):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_top_posts(self, subreddit_name: str, limit: int = 10, time: str = '') -> list[Post]:
        """Get top posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.top(subreddit_name, limit, time=time):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_rising_posts(self, subreddit_name: str, limit: int = 10) -> list[Post]:
        """Get rising posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.rising(subreddit_name, limit):
            posts.append(self._build_post(subm))
        return posts

    def get_post_content(self, post_id: str, comment_limit: int = 10, comment_depth: int = 3) -> PostDetail:
        """Get detailed content of a specific post including comments"""
        submission = self.client.p.submission.fetch(post_id)
        post = self._build_post(submission)

        # Fetch comments
        comments = self.get_post_comments(post_id, comment_limit)
        
        return PostDetail(post=post, comments=comments)

    def get_post_comments(self, post_id: str, limit: int = 10) -> list[Comment]:
        """Get comments from a post"""
        comments = []
        tree_node = self.client.p.comment_tree.fetch(post_id, sort='top', limit=limit)
        for node in tree_node.children:
            comment = self._build_comment_tree(node)
            if comment:
                comments.append(comment)
        return comments


mcp_server = FastMCP("mcp-reddit")
reddit_server = RedditServer()


@mcp_server.tool
async def get_frontpage_posts(limit: int = 10) -> list[TextContent]:
    """Get hot posts from Reddit frontpage"""
    try:
        posts = reddit_server.get_frontpage_posts(limit)
        return posts
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching frontpage posts: {e}")]


@mcp_server.tool
async def get_subreddit_info(subreddit_name: str) -> list[TextContent]:
    """Get information about a subreddit"""
    
    try:
        info = reddit_server.get_subreddit_info(subreddit_name)
        return info
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching subreddit info: {e}")]

@mcp_server.tool
async def get_subreddit_hot_posts(subreddit_name: str, limit: int = 10) -> list[TextContent]:
    """Get hot posts from a specific subreddit"""
    try:
        posts = reddit_server.get_subreddit_hot_posts(subreddit_name, limit)
        return posts
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching subreddit hot posts: {e}")]

@mcp_server.tool
async def get_subreddit_new_posts(subreddit_name: str, limit: int = 10) -> list[TextContent]:
    """Get new posts from a specific subreddit"""
    try:
        posts = reddit_server.get_subreddit_new_posts(subreddit_name, limit)
        return posts
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching subreddit new posts: {e}")]

@mcp_server.tool
async def get_subreddit_top_posts(subreddit_name: str, limit: int = 10) -> list[TextContent]:
    """Get top posts from a specific subreddit"""
    try:
        posts = reddit_server.get_subreddit_top_posts(subreddit_name, limit)
        return posts
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching subreddit top posts: {e}")]

@mcp_server.tool
async def get_subreddit_rising_posts(subreddit_name: str, limit: int = 10) -> list[TextContent]:
    """Get rising posts from a specific subreddit"""
    try:
        posts = reddit_server.get_subreddit_rising_posts(subreddit_name, limit)
        return posts
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching subreddit rising posts: {e}")]

# Check how we are getting post ids??
@mcp_server.tool
async def get_post_content(post_id: str, comment_limit: int = 10, comment_depth: int = 3) -> list[TextContent]:
    """Get detailed content of a specific post including comments"""
    try:
        detail = reddit_server.get_post_content(post_id, comment_limit, comment_depth)
        return detail
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching post content: {e}")]

@mcp_server.tool
async def get_post_comments(post_id: str, limit: int = 10) -> list[TextContent]:
    """Get comments for a specific post"""
    try:
        comments = reddit_server.get_post_comments(post_id, limit)
        return comments
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching post comments: {e}")]

app = mcp_server.http_app(path="/mcp/reddit_server", stateless_http=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    # https://github.com/Hawstein/mcp-server-reddit/tree/main
    uvicorn.run(app, host="127.0.0.1", port=8000)