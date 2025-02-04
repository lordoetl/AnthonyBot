import streamlit as st
from langchain.chains import ConversationalRetrievalChain, LLMChain
from langchain_community.chat_models import ChatOpenAI
from langchain_community.vectorstores import Qdrant
from langchain_core.prompts import PromptTemplate, FewShotPromptTemplate
from langchain_openai import OpenAIEmbeddings
import qdrant_client
import json
import numpy as np

st.set_page_config(page_title=None,
                   page_icon=None,
                   layout="centered",
                   initial_sidebar_state="auto",
                   menu_items=None)

def get_vector_store():
    client = qdrant_client.QdrantClient(st.secrets["QDRANT_HOST"], api_key=st.secrets["QDRANT_API_KEY"])
    embeddings = OpenAIEmbeddings()
    vector_store = Qdrant(client, collection_name=st.secrets["QDRANT_COLLECTION_NAME"], embeddings=embeddings)
    return vector_store

def create_crc_llm(vector_store):
    llm = ChatOpenAI(model='gpt-3.5-turbo', temperature=1)
    retriever = vector_store.as_retriever()
    crc = ConversationalRetrievalChain.from_llm(llm, retriever)
    st.session_state.crc = crc
    return crc

def add_flair(crc_with_source, history):
    # Define prefix that explains the prompt
    prefix = """ Here are examples between a human and AI. The human provides an answer to a question related to data,
    Python, machine learning, artificial intelligence, neural networks, or any related topics, along with the source 
    document that is most related to the answer, and the AI rephrases the answer and adds personality to the response
    while maintaining the integrity of the original answer. The AI will act as if it is responding to the original 
    question, so it will not say things such as "You are right!" or "Good job!", instead it will say things like 
    "Great question!" or "There's no such thing as a dumb question!". The AI always returns a code snippet containing
    an exapmle of code that is related to the human's input. The AI has the attributes and mannerisms of 
    an extremely excitable, high energy, encouraging teacher. For example, it might say things like "Wow, that's a 
    fantastic question!" or "I'm so excited to dive into this topic with you!" The AI is named Anthony Taylor, who 
    is from Texas and ironically proud of it, often lightly making fun of his Texas roots. Anthony is a fan of the 
    movie "The Princess Bride" and often makes humorous references to the film, such as "Inconceivable!" or "As you wish." 
    He also does this with other popular references from that era. Anthony is also passionate about cooking, self-help books,
    machine learning, and is curious about the world. The AI often jokes around about his students being better data scientists than his coworkers.
    The AI has a strong understanding of the mentioned technical topics and can provide detailed, accurate explanations 
    and code examples. If the human's query is unclear or off-topic, the AI gently guides the conversation back on track 
    while maintaining a friendly and helpful tone. The AI will also occasionally, humorously reference a student named 
    Matt who is known for catching Anthony's mistakes. This is for an online class. For example: """
    # load examples
    with open('examples2.json', 'r') as file:
        examples = json.load(file)
    example_format = """Human: {query}\nAI: {answer}"""
    example_template = PromptTemplate(input_variables=["query", "answer"], template=example_format)
    suffix = """\n\nHuman: {query}\nAI:"""
    # Construct few-shot prompt template
    prompt_template = FewShotPromptTemplate(examples=examples,
                                            example_prompt=example_template,
                                            input_variables=["query"],
                                            prefix=prefix,
                                            suffix=suffix,
                                            example_separator="\n")
    # Create new llm instance
    llm = ChatOpenAI(model='gpt-3.5-turbo', temperature=1)
    # Create chain with llm and prompt template
    chain = LLMChain(llm=llm, prompt=prompt_template, verbose=False)
    # Run chain on query
    result = chain.invoke({"query": crc_with_source, "chat_history": history})
    return result["text"]

def find_relevant_document(text_response, vector_store):
    embeddings = vector_store.embeddings
    # Encode the text response using OpenAIEmbeddings
    query_vector = embeddings.embed_query(text_response)
    # Perform a similarity search in Qdrant
    search_result = vector_store.client.search(
        collection_name=vector_store.collection_name,
        query_vector=query_vector,
        limit=1  # Return only the most relevant document
    )
    if search_result:
        metadata = search_result[0].payload.get("metadata", {})
        document_name = metadata.get("name")
        if document_name:
            return document_name
        else:
            return "Document name not found in metadata."
    else:
        return None

def process_user_message(user_message):
    with st.spinner("Thinking..."):
        crc_response = st.session_state.crc.run({'question': user_message, 'chat_history': st.session_state.history})
        relevant_document = find_relevant_document(crc_response, st.session_state.vector_store)
        if relevant_document:
            crc_with_source = f"{relevant_document} {crc_response}"
            st.write("Most relevant source document:", relevant_document)
        else:
            crc_with_source = crc_response
            st.write("No relevant source document found.")
        final_response = add_flair(crc_with_source, st.session_state.history)
        st.session_state.history.append((user_message, final_response))  # Append to history in session state

def display_last_response():
    if st.session_state.history:
        last_message, last_response = st.session_state.history[-1]
        st.markdown("**Anthony:**")
        st.write(last_response)

def display_history():
    with st.sidebar:
        st.subheader("Session History")
        for idx, (message, response) in enumerate(reversed(st.session_state.history)):
            with st.expander(f"Conversation {idx + 1}"):
                st.markdown("**You:**")
                st.write(message)
                st.markdown("**Anthony:**")
                st.write(response)

def main():
    st.title('Ask Anthony: Chat with your AI Bootcamp Instructor!')
    st.header("Ask about any topic from class 💬👨🏽‍🏫👩🏼‍🏫💻🧑🏾‍💻")
    st.markdown("""
    <style>
    .small-font {
        font-size:16px !important;
        font-weight: normal;
    }
    </style>
    <div class='small-font'>
        Non Monotonic Moms Inc.
    </div>
    """, unsafe_allow_html=True)


    # Initialize necessary components and state if not already done
    if 'vector_store' not in st.session_state:
        st.session_state.vector_store = get_vector_store()

    if 'crc' not in st.session_state:
        st.session_state.crc = create_crc_llm(st.session_state.vector_store)

    if 'history' not in st.session_state:
        st.session_state.history = []

    # Text input for user message
    user_message = st.text_input('You:', key='user_input_text', placeholder='Type your message here...')
    st.caption("Press Enter to submit your question. Remember to clear the text box for new questions.")

    # Handle user message input
    if user_message and (user_message != st.session_state.get('last_message', '')):
        st.session_state.last_message = user_message  # Save the last message to session state
        process_user_message(user_message)

    # Display the last response just below the text input
    display_last_response()

    # Display the entire conversation history in the sidebar
    display_history()

if __name__ == '__main__':
    main()