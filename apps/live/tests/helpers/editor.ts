import { IncomingMessage, MessageType, OutgoingMessage } from "@hocuspocus/server";
import WebSocket from "ws";
import * as Y from "yjs";
import { SAVE_STATUS } from "@plane/editor";

/**
 * An editor of a document, as far as the tests need one: a WebSocket connection that sends its
 * changes of the document to the server and keeps the stateless messages it gets.
 */
export class Editor {
  // The first one is the answer to the status request the editor opens with.
  messages: string[] = [];
  private document = new Y.Doc();

  private constructor(
    private readonly socket: WebSocket,
    private readonly documentName: string
  ) {
    socket.on("message", (data: Buffer) => {
      const message = new IncomingMessage(data);
      message.readVarString();
      if (message.readVarUint() === MessageType.Stateless) {
        this.messages.push(message.readVarString());
      }
    });
    this.document.on("update", (update: Uint8Array) => {
      socket.send(new OutgoingMessage(documentName).createSyncMessage().writeUpdate(update).toUint8Array());
    });
  }

  /**
   * Connects to the server and waits for its first answer.
   * @param token What the server authenticates the editor by, when it does
   */
  static async open(url: string, documentName: string, token?: string): Promise<Editor> {
    const socket = new WebSocket(url);
    await new Promise((resolve, reject) => socket.once("open", resolve).once("error", reject));
    const editor = new Editor(socket, documentName);
    if (token) {
      // the token message of the Hocuspocus provider
      const message = new IncomingMessage(new Uint8Array());
      message.writeVarString(documentName);
      message.writeVarUint(MessageType.Auth);
      message.writeVarUint(0);
      message.writeVarString(token);
      socket.send(message.toUint8Array());
    }
    const answered = new Promise((resolve) => socket.once("message", resolve));
    editor.requestSaveStatus();
    await answered;
    // the token is answered first, the status request after it
    while (editor.messages.length === 0) {
      await new Promise((resolve) => socket.once("message", resolve));
    }
    return editor;
  }

  type(text: string) {
    const paragraph = new Y.XmlElement("paragraph");
    paragraph.insert(0, [new Y.XmlText(text)]);
    this.document.getXmlFragment("default").push([paragraph]);
  }

  requestSaveStatus() {
    this.socket.send(new OutgoingMessage(this.documentName).writeStateless(SAVE_STATUS.request).toUint8Array());
  }

  async close() {
    await new Promise((resolve) => this.socket.once("close", resolve).close());
  }
}
