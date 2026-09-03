import { FC } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './MessageContent.scss';

interface MessageContentProps {
  content: string;
}

const MessageContent: FC<MessageContentProps> = ({ content }) => {
  return (
    <div className="message-content-wrapper">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Customize link rendering to open in new tab
          a: ({ node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
          // Style strong/bold text
          strong: ({ node, ...props }) => (
            <strong {...props} className="markdown-bold" />
          ),
          // Style ordered lists
          ol: ({ node, ...props }) => (
            <ol {...props} className="markdown-list" />
          ),
          // Style list items
          li: ({ node, ...props }) => (
            <li {...props} className="markdown-list-item" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MessageContent;