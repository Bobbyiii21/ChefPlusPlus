/**
 * Bedrock model IDs for RAG (embeddings + chat). Enable models in the Bedrock console for your region.
 * @see https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html
 */
export const BEDROCK_MODELS = {
  /** Amazon Titan for knowledge-base vector embeddings (separate from the chat model). */
  embeddingModelId: 'amazon.titan-embed-text-v1',
  /** Qwen3 dense 32B — general/chat; not a Qwen3-Coder variant. */
  qwenChatModelId: 'qwen.qwen3-32b-v1:0',
} as const;

/** OpenSearch Serverless index + field names for the Bedrock KB (created/used on sync). */
export const BEDROCK_KB_VECTOR = {
  vectorIndexName: 'bedrock-knowledge-base-default-index',
  vectorField: 'bedrock-knowledge-base-default-vector',
  textField: 'text',
  metadataField: 'metadata',
} as const;
