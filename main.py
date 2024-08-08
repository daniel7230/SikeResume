import langchain
import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def get_pdf_text(pdf_file):
    text = ""
    pdf_reader = PdfReader(pdf_file)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text


def get_text_chunks(raw_text):
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=3000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(raw_text)
    return chunks


def get_vectorstore(text_chunks):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore


def get_conversation_chain(vectorstore):
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain


def handle_user_input(job_description, vectorstore):
    # Reinitialize the conversation chain for a fresh start
    conversation_chain = get_conversation_chain(vectorstore)

    # Retrieve relevant chunks from the vectorstore based on the job description
    relevant_chunks = vectorstore.similarity_search(job_description, k=5)

    # Combine the relevant chunks into a single text block
    retrieved_text = "\n\n".join([chunk.page_content for chunk in relevant_chunks])

    prompt = f"""
    Given the following relevant sections from the resume and the job description, suggest specific content changes to the resume to better match the job requirements. 
    Focus only on modifying, adding, or removing content to align with the job description. Do not suggest formatting changes.

    Relevant Resume Sections:
    {retrieved_text}

    Job Description:
    {job_description}

    Please provide your suggestions using the following HTML and Markdown format:

    <h2>Suggested Change 1 : [Brief explanation about the change]</h2>
    <ul>
        <li><span style="color: hsl(0, 70%, 85%);">Current Content: [Relevant excerpt from the resume]</span></li>
        <li><span style="color: hsl(120, 70%, 85%);">Proposed Change: [Suggested modification or addition]</span></li>
        <li><span style="color: hsl(210, 70%, 85%);">Reason: [Brief explanation of why this change aligns better with the job description]</span></li>
    </ul>

    <h2> Suggested Change 2 : [Brief explanation about the change]</h2>
    <ul>
        <li><span style="color: hsl(0, 70%, 85%);">Current Content: [Relevant excerpt from the resume]</span></li>
        <li><span style="color: hsl(120, 70%, 85%);">Proposed Change: [Suggested modification or addition]</span></li>
        <li><span style="color: hsl(210, 70%, 85%);">Reason: [Brief explanation of why this change aligns better with the job description]</span></li>
    </ul>

    ... (continue for all suggested changes)

    Remember to focus solely on content changes that make the resume more relevant to the specific job description.
    Use the HTML color tags as shown above to format your suggestions.

    And also return an 'Additional Projects' section. This should consist of 3 possible projects that can be added on the resume which uses the skills from both the original resume and the job description. Quantify the results.
    The projects should be of some real-world use case. Do not generate generic project names and descriptions. Be creative.
    Give this in the same format as the projects in the original resume. I should be able to just copy and paste it directly on the resume.
    Also, mention the reason why adding each project would benefit me.
    """

    response = conversation_chain.invoke({
        'question': prompt
    })
    st.session_state.chat_history = response['chat_history']

    # Ensure suggestions are retrieved correctly
    for i, message in enumerate(st.session_state.chat_history):
        if (i % 2 != 0):  # Typically, odd-indexed messages in chat history are model responses
            st.session_state.latest_suggestion = message.content



def main():
    load_dotenv()

    langchain.debug = False
    st.set_page_config(page_title="SikeResume", page_icon=":ghost:")

    # Initialize session state variables if they don't exist
    # if "conversation" not in st.session_state:
    #     st.session_state.conversation = None

    if "vectorstore" not in st.session_state:
         st.session_state.vectorstore = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None

    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None

    if "latest_suggestion" not in st.session_state:
        st.session_state.latest_suggestion = ""

    if "resume_text" not in st.session_state:
        st.session_state.resume_text = ""

    if "job_description" not in st.session_state:
        st.session_state.job_description = ""

    st.header("SikeResume - Tweak it till you make it :chart_with_upwards_trend:")

    with st.sidebar:
        st.info("Step 1: Upload your resume here and process it.")
        uploaded_file = st.file_uploader("Upload your Resume here and click on 'Process'", type=["pdf"],
                                         accept_multiple_files=False)

        if uploaded_file is not None:
            st.session_state.uploaded_file = uploaded_file

        if st.button("Process"):
            if st.session_state.uploaded_file is not None:
                with st.spinner("Processing"):
                    raw_text = get_pdf_text(st.session_state.uploaded_file)
                    st.session_state.resume_text = raw_text
                    text_chunks = get_text_chunks(raw_text)
                    st.session_state.vectorstore = get_vectorstore(text_chunks)
                    # st.session_state.conversation = get_conversation_chain(vectorstore)
                st.success("Processing complete!")
            else:
                st.warning("Please upload a resume before processing.")

    # Display uploaded file name (if any)
    if st.session_state.uploaded_file:
        st.sidebar.write(f"Current resume: {st.session_state.uploaded_file.name}")

    st.info("Step 2: Paste the job description and click the 'Submit' button.")
    # Initialize job description text area
    job_description = st.text_area(
        "Job Description:",
        height=200,
        value=st.session_state.get("job_description", ""),
        key="job_description"
    )

    if st.button("Submit"):
        if st.session_state.resume_text is None or st.session_state.resume_text == "":
            st.warning("Please upload and process a resume before submitting a job description.")
        elif job_description.strip() != "":
            handle_user_input(job_description, st.session_state.vectorstore)
        else:
            st.warning("Please paste the job description and then submit.")

    if st.session_state.latest_suggestion:
        st.markdown(st.session_state.latest_suggestion, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
