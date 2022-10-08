DEFAULT_TAILER_CONFIG = \
    '''
    channels:
       - name: Application
         query: "*"
       - name: System
         query: "*"
    lookback: -1           # start-at-oldest
    bookmarks_file: null   # bookmarks not used
    transforms:
        - winevt_tailer.transforms.xml_remove_binary
        - winevt_tailer.transforms.xml_to_json
    '''

DEFAULT_LOGGING_CONFIG = \
    '''
    version: 1
    disable_existing_loggers: true
    formatters:
      simple:
        format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    handlers:
      console:
        class: logging.StreamHandler
        level: INFO
        formatter: simple
        stream: ext://sys.stderr
    root:
      level: DEBUG
      handlers: [console]
    '''

XSLT_XML_TO_JSON = \
    '''
    <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
      <xsl:output method="text"/>
      <xsl:strip-space elements="*"/>
      <xsl:template match="*">
        <xsl:if test="position() != 1">, </xsl:if>
        <xsl:value-of select="concat('{&quot;',
          local-name(),
          '&quot;: ')"/>
        <xsl:choose>
          <xsl:when test="count(node()) > 1">
            <xsl:text>[</xsl:text>
            <xsl:apply-templates/>
            <xsl:text>]</xsl:text>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates/>
          </xsl:otherwise>
        </xsl:choose>
        <xsl:text>}</xsl:text>
      </xsl:template>
      <xsl:template match="text()">
        <xsl:if test="position() != 1">, </xsl:if>
        <xsl:value-of select="concat('&quot;', 
          normalize-space(), 
          '&quot;')"/>
      </xsl:template>
    </xsl:stylesheet>
    '''
